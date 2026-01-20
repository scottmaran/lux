use anyhow::{Context, Result};
use aya::{maps::RingBuf, programs::TracePoint, Bpf};
use bytemuck::{Pod, Zeroable};
use serde_json::json;
use signal_hook::consts::signal::{SIGINT, SIGTERM};
use signal_hook::flag;
use std::env;
use std::fs::{self, OpenOptions};
use std::io::{BufWriter, Write};
use std::net::{Ipv4Addr, Ipv6Addr};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime};

const TASK_COMM_LEN: usize = 16;
const DNS_PAYLOAD_MAX: usize = 512;
const UNIX_PATH_MAX: usize = 108;

const AF_UNIX: u16 = 1;
const AF_INET: u16 = 2;
const AF_INET6: u16 = 10;

const IPPROTO_TCP: u8 = 6;
const IPPROTO_UDP: u8 = 17;

const EVENT_NET_CONNECT: u8 = 1;
const EVENT_NET_SEND: u8 = 2;
const EVENT_DNS_QUERY: u8 = 3;
const EVENT_DNS_RESPONSE: u8 = 4;
const EVENT_UNIX_CONNECT: u8 = 5;

#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable)]
struct Event {
    event_type: u8,
    family: u8,
    protocol: u8,
    _pad: u8,
    pid: u32,
    uid: u32,
    gid: u32,
    cgroup_id: u64,
    ts: u64,
    syscall_result: i64,
    src_addr: [u8; 16],
    dst_addr: [u8; 16],
    src_port: u16,
    dst_port: u16,
    bytes: u32,
    comm: [u8; TASK_COMM_LEN],
    unix_path_len: u16,
    unix_path: [u8; UNIX_PATH_MAX],
    dns_payload_len: u16,
    dns_payload: [u8; DNS_PAYLOAD_MAX],
}

fn main() -> Result<()> {
    set_memlock_rlimit().context("set memlock rlimit")?;

    let bpf_path = env::var("COLLECTOR_EBPF_BPF")
        .unwrap_or_else(|_| "/usr/local/share/collector/collector-ebpf.o".to_string());
    let output_path = env::var("COLLECTOR_EBPF_OUTPUT")
        .unwrap_or_else(|_| "/logs/ebpf.jsonl".to_string());

    let mut bpf = Bpf::load_file(&bpf_path).context("load ebpf object")?;

    attach_tracepoint(&mut bpf, "sys_enter_connect")?;
    attach_tracepoint(&mut bpf, "sys_exit_connect")?;
    attach_tracepoint(&mut bpf, "sys_enter_sendto")?;
    attach_tracepoint(&mut bpf, "sys_exit_sendto")?;
    attach_tracepoint(&mut bpf, "sys_enter_recvfrom")?;
    attach_tracepoint(&mut bpf, "sys_exit_recvfrom")?;

    let mut ring = RingBuf::new(bpf.map_mut("EVENTS")?).context("open ring buffer")?;

    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&output_path)
        .with_context(|| format!("open output file {output_path}"))?;
    let mut writer = BufWriter::new(file);

    let running = Arc::new(AtomicBool::new(true));
    flag::register(SIGINT, Arc::clone(&running)).context("register SIGINT")?;
    flag::register(SIGTERM, Arc::clone(&running)).context("register SIGTERM")?;

    while running.load(Ordering::Relaxed) {
        if let Some(item) = ring.next() {
            let data = &*item;
            if data.len() >= std::mem::size_of::<Event>() {
                let event = *bytemuck::from_bytes::<Event>(
                    &data[..std::mem::size_of::<Event>()],
                );
                if let Some(line) = render_event(&event) {
                    writer.write_all(line.as_bytes())?;
                    writer.write_all(b"\n")?;
                }
            }
        } else {
            std::thread::sleep(Duration::from_millis(50));
        }
    }

    writer.flush()?;
    Ok(())
}

fn attach_tracepoint(bpf: &mut Bpf, name: &str) -> Result<()> {
    let program: &mut TracePoint = bpf.program_mut(name)?.try_into()?;
    program.load()?;
    program.attach("syscalls", name)?;
    Ok(())
}

fn render_event(event: &Event) -> Option<String> {
    let ts = format_ts(event.ts);
    let comm = bytes_to_string(&event.comm);
    let pid = event.pid;
    let ppid = read_ppid(pid).unwrap_or(0);
    let uid = event.uid;
    let gid = event.gid;
    let cgroup_id = format!("0x{0:016x}", event.cgroup_id);
    let syscall_result = event.syscall_result;

    match event.event_type {
        EVENT_NET_CONNECT => Some(
            json!({
                "schema_version": "ebpf.v1",
                "ts": ts,
                "event_type": "net_connect",
                "pid": pid,
                "ppid": ppid,
                "uid": uid,
                "gid": gid,
                "comm": comm,
                "cgroup_id": cgroup_id,
                "syscall_result": syscall_result,
                "net": {
                    "protocol": protocol_to_string(event.protocol),
                    "family": family_to_string(event.family as u16),
                    "src_ip": addr_to_string(event.family as u16, &event.src_addr),
                    "src_port": event.src_port,
                    "dst_ip": addr_to_string(event.family as u16, &event.dst_addr),
                    "dst_port": event.dst_port
                }
            })
            .to_string(),
        ),
        EVENT_NET_SEND => Some(
            json!({
                "schema_version": "ebpf.v1",
                "ts": ts,
                "event_type": "net_send",
                "pid": pid,
                "ppid": ppid,
                "uid": uid,
                "gid": gid,
                "comm": comm,
                "cgroup_id": cgroup_id,
                "syscall_result": syscall_result,
                "net": {
                    "protocol": protocol_to_string(event.protocol),
                    "family": family_to_string(event.family as u16),
                    "src_ip": addr_to_string(event.family as u16, &event.src_addr),
                    "src_port": event.src_port,
                    "dst_ip": addr_to_string(event.family as u16, &event.dst_addr),
                    "dst_port": event.dst_port,
                    "bytes": event.bytes
                }
            })
            .to_string(),
        ),
        EVENT_DNS_QUERY => {
            let payload = dns_payload(event);
            let parsed = parse_dns(&payload);
            Some(
                json!({
                    "schema_version": "ebpf.v1",
                    "ts": ts,
                    "event_type": "dns_query",
                    "pid": pid,
                    "ppid": ppid,
                    "uid": uid,
                    "gid": gid,
                    "comm": comm,
                    "cgroup_id": cgroup_id,
                    "syscall_result": syscall_result,
                    "dns": {
                        "transport": "udp",
                        "query_name": parsed.query_name.unwrap_or_else(|| "".to_string()),
                        "query_type": parsed.query_type.unwrap_or_else(|| "".to_string()),
                        "server_ip": addr_to_string(event.family as u16, &event.dst_addr),
                        "server_port": event.dst_port
                    }
                })
                .to_string(),
            )
        }
        EVENT_DNS_RESPONSE => {
            let payload = dns_payload(event);
            let parsed = parse_dns(&payload);
            Some(
                json!({
                    "schema_version": "ebpf.v1",
                    "ts": ts,
                    "event_type": "dns_response",
                    "pid": pid,
                    "ppid": ppid,
                    "uid": uid,
                    "gid": gid,
                    "comm": comm,
                    "cgroup_id": cgroup_id,
                    "syscall_result": syscall_result,
                    "dns": {
                        "transport": "udp",
                        "query_name": parsed.query_name.unwrap_or_else(|| "".to_string()),
                        "query_type": parsed.query_type.unwrap_or_else(|| "".to_string()),
                        "rcode": parsed.rcode.unwrap_or_else(|| "".to_string()),
                        "answers": parsed.answers
                    }
                })
                .to_string(),
            )
        }
        EVENT_UNIX_CONNECT => {
            let (path, abstract_flag) = unix_path(event);
            Some(
                json!({
                    "schema_version": "ebpf.v1",
                    "ts": ts,
                    "event_type": "unix_connect",
                    "pid": pid,
                    "ppid": ppid,
                    "uid": uid,
                    "gid": gid,
                    "comm": comm,
                    "cgroup_id": cgroup_id,
                    "syscall_result": syscall_result,
                    "unix": {
                        "path": path,
                        "abstract": abstract_flag,
                        "sock_type": "stream"
                    }
                })
                .to_string(),
            )
        }
        _ => None,
    }
}

fn dns_payload(event: &Event) -> Vec<u8> {
    let len = event.dns_payload_len as usize;
    event.dns_payload[..len].to_vec()
}

fn bytes_to_string(bytes: &[u8]) -> String {
    let end = bytes.iter().position(|b| *b == 0).unwrap_or(bytes.len());
    String::from_utf8_lossy(&bytes[..end]).to_string()
}

fn addr_to_string(family: u16, addr: &[u8; 16]) -> String {
    match family {
        AF_INET => Ipv4Addr::new(addr[0], addr[1], addr[2], addr[3]).to_string(),
        AF_INET6 => Ipv6Addr::from(*addr).to_string(),
        _ => "".to_string(),
    }
}

fn protocol_to_string(proto: u8) -> &'static str {
    match proto {
        IPPROTO_TCP => "tcp",
        IPPROTO_UDP => "udp",
        _ => "unknown",
    }
}

fn family_to_string(family: u16) -> &'static str {
    match family {
        AF_INET => "ipv4",
        AF_INET6 => "ipv6",
        _ => "unknown",
    }
}

fn unix_path(event: &Event) -> (String, bool) {
    let len = event.unix_path_len as usize;
    if len == 0 {
        return ("".to_string(), false);
    }

    let path_bytes = &event.unix_path[..UNIX_PATH_MAX];
    if path_bytes[0] == 0 {
        let start = 1;
        let end = start + len.min(UNIX_PATH_MAX - 1);
        (
            String::from_utf8_lossy(&path_bytes[start..end]).to_string(),
            true,
        )
    } else {
        (
            String::from_utf8_lossy(&path_bytes[..len.min(UNIX_PATH_MAX)]).to_string(),
            false,
        )
    }
}

fn format_ts(event_ts: u64) -> String {
    let now_wall = SystemTime::now();
    let now_mono = monotonic_now_ns();
    let event_wall = if now_mono >= event_ts {
        now_wall
            .checked_sub(Duration::from_nanos(now_mono - event_ts))
            .unwrap_or(now_wall)
    } else {
        now_wall
    };

    let datetime: time::OffsetDateTime = event_wall.into();
    datetime
        .format(&time::format_description::well_known::Rfc3339)
        .unwrap_or_else(|_| "".to_string())
}

fn monotonic_now_ns() -> u64 {
    let mut ts = libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    unsafe {
        libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut ts);
    }
    (ts.tv_sec as u64) * 1_000_000_000 + (ts.tv_nsec as u64)
}

fn set_memlock_rlimit() -> Result<()> {
    let rlim = libc::rlimit {
        rlim_cur: libc::RLIM_INFINITY,
        rlim_max: libc::RLIM_INFINITY,
    };
    let ret = unsafe { libc::setrlimit(libc::RLIMIT_MEMLOCK, &rlim) };
    if ret != 0 {
        return Err(anyhow::anyhow!("setrlimit failed"));
    }
    Ok(())
}

fn read_ppid(pid: u32) -> Option<u32> {
    let path = format!("/proc/{pid}/stat");
    let content = fs::read_to_string(path).ok()?;
    let end = content.rfind(')')?;
    let rest = &content[end + 1..];
    let mut parts = rest.split_whitespace();
    let _state = parts.next()?;
    let ppid = parts.next()?;
    ppid.parse::<u32>().ok()
}

#[derive(Default)]
struct DnsParsed {
    query_name: Option<String>,
    query_type: Option<String>,
    rcode: Option<String>,
    answers: Vec<String>,
}

fn parse_dns(payload: &[u8]) -> DnsParsed {
    let mut parsed = DnsParsed::default();
    if payload.len() < 12 {
        return parsed;
    }

    let flags = u16::from_be_bytes([payload[2], payload[3]]);
    parsed.rcode = Some(rcode_to_string((flags & 0x0f) as u8));

    let qdcount = u16::from_be_bytes([payload[4], payload[5]]) as usize;
    let ancount = u16::from_be_bytes([payload[6], payload[7]]) as usize;

    let mut offset = 12usize;
    if qdcount > 0 {
        if let Some((name, new_offset)) = read_dns_name(payload, offset, 0) {
            parsed.query_name = Some(name);
            offset = new_offset;
            if payload.len() >= offset + 4 {
                let qtype = u16::from_be_bytes([payload[offset], payload[offset + 1]]);
                parsed.query_type = Some(qtype_to_string(qtype));
                offset += 4;
            }
        }
    }

    let mut answers = Vec::new();
    let mut i = 0usize;
    while i < ancount {
        if let Some((_, new_offset)) = read_dns_name(payload, offset, 0) {
            offset = new_offset;
        } else {
            break;
        }
        if payload.len() < offset + 10 {
            break;
        }
        let atype = u16::from_be_bytes([payload[offset], payload[offset + 1]]);
        let rdlen = u16::from_be_bytes([payload[offset + 8], payload[offset + 9]]) as usize;
        offset += 10;
        if payload.len() < offset + rdlen {
            break;
        }
        if atype == 1 && rdlen == 4 {
            let ip = Ipv4Addr::new(
                payload[offset],
                payload[offset + 1],
                payload[offset + 2],
                payload[offset + 3],
            );
            answers.push(ip.to_string());
        } else if atype == 28 && rdlen == 16 {
            let mut addr = [0u8; 16];
            addr.copy_from_slice(&payload[offset..offset + 16]);
            answers.push(Ipv6Addr::from(addr).to_string());
        }
        offset += rdlen;
        i += 1;
        if answers.len() >= 4 {
            break;
        }
    }

    parsed.answers = answers;
    parsed
}

fn read_dns_name(payload: &[u8], mut offset: usize, depth: u8) -> Option<(String, usize)> {
    if depth > 5 {
        return None;
    }

    let mut labels: Vec<String> = Vec::new();
    let mut jumped = false;
    let mut jump_offset = 0usize;

    loop {
        if offset >= payload.len() {
            return None;
        }
        let len = payload[offset];
        if len == 0 {
            offset += 1;
            break;
        }
        if len & 0xc0 == 0xc0 {
            if offset + 1 >= payload.len() {
                return None;
            }
            let ptr = (((len & 0x3f) as usize) << 8) | payload[offset + 1] as usize;
            if !jumped {
                jump_offset = offset + 2;
            }
            offset = ptr;
            jumped = true;
            continue;
        }
        let label_len = len as usize;
        offset += 1;
        if offset + label_len > payload.len() {
            return None;
        }
        let label = String::from_utf8_lossy(&payload[offset..offset + label_len]).to_string();
        labels.push(label);
        offset += label_len;
    }

    let name = labels.join(".");
    if jumped {
        Some((name, jump_offset))
    } else {
        Some((name, offset))
    }
}

fn qtype_to_string(qtype: u16) -> String {
    match qtype {
        1 => "A".to_string(),
        28 => "AAAA".to_string(),
        5 => "CNAME".to_string(),
        15 => "MX".to_string(),
        16 => "TXT".to_string(),
        _ => format!("TYPE{qtype}"),
    }
}

fn rcode_to_string(rcode: u8) -> String {
    match rcode {
        0 => "NOERROR".to_string(),
        1 => "FORMERR".to_string(),
        2 => "SERVFAIL".to_string(),
        3 => "NXDOMAIN".to_string(),
        4 => "NOTIMP".to_string(),
        5 => "REFUSED".to_string(),
        _ => format!("RCODE{rcode}"),
    }
}
