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
#[derive(Copy, Clone)]
struct Event {
    event_type: u8,
    family: u8,
    protocol: u8,
    _pad: u8,
    pid: u32,
    fd: i32,
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

unsafe impl Zeroable for Event {}
unsafe impl Pod for Event {}

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

    let mut ring = RingBuf::try_from(
        bpf.map_mut("EVENTS").context("missing EVENTS map")?,
    )
    .context("open ring buffer")?;

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
    let program: &mut TracePoint = bpf
        .program_mut(name)
        .context(format!("missing program {name}"))?
        .try_into()?;
    program.load()?;
    program.attach("syscalls", name)?;
    Ok(())
}

struct NetFields {
    protocol: String,
    family: String,
    src_ip: String,
    src_port: u16,
    dst_ip: String,
    dst_port: u16,
}

fn merge_net_fields(event: &Event, socket: Option<SocketInfo>) -> NetFields {
    let mut protocol = protocol_to_string(event.protocol).to_string();
    let mut family = family_to_string(event.family as u16).to_string();
    let mut src_ip = addr_to_string(event.family as u16, &event.src_addr);
    let mut dst_ip = addr_to_string(event.family as u16, &event.dst_addr);
    let mut src_port = event.src_port;
    let mut dst_port = event.dst_port;
    let mut src_missing = src_ip.is_empty() || is_zero_ip(&src_ip);
    let mut dst_missing = dst_ip.is_empty() || is_zero_ip(&dst_ip);

    if let Some(info) = socket {
        if protocol == "unknown" {
            protocol = info.protocol.to_string();
        }
        if family == "unknown" {
            family = family_to_string(info.family).to_string();
        }
        if src_port == 0 || src_missing {
            src_port = info.local_port;
            if src_missing {
                src_ip = info.local_ip;
            }
        }
        if dst_port == 0 || dst_missing {
            dst_port = info.remote_port;
            if dst_missing {
                dst_ip = info.remote_ip;
            }
        }
    }

    NetFields {
        protocol,
        family,
        src_ip,
        src_port,
        dst_ip,
        dst_port,
    }
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
        EVENT_NET_CONNECT => {
            let socket = socket_info(pid, event.fd);
            let net = merge_net_fields(event, socket);
            Some(
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
                        "protocol": net.protocol,
                        "family": net.family,
                        "src_ip": net.src_ip,
                        "src_port": net.src_port,
                        "dst_ip": net.dst_ip,
                        "dst_port": net.dst_port
                    }
                })
                .to_string(),
            )
        }
        EVENT_NET_SEND => {
            let socket = socket_info(pid, event.fd);
            let net = merge_net_fields(event, socket);
            Some(
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
                        "protocol": net.protocol,
                        "family": net.family,
                        "src_ip": net.src_ip,
                        "src_port": net.src_port,
                        "dst_ip": net.dst_ip,
                        "dst_port": net.dst_port,
                        "bytes": event.bytes
                    }
                })
                .to_string(),
            )
        }
        EVENT_DNS_QUERY => {
            let payload = dns_payload(event);
            let (dns_bytes, mut transport) = dns_payload_view(&payload);
            let parsed = parse_dns(dns_bytes);
            let socket = socket_info(pid, event.fd);
            if transport == "udp" {
                if let Some(info) = socket.as_ref() {
                    if info.protocol == "tcp" {
                        transport = "tcp";
                    }
                }
            }
            let (server_ip, server_port) = dns_server_info(event, socket.as_ref(), true);
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
                        "transport": transport,
                        "query_name": parsed.query_name.unwrap_or_else(|| "".to_string()),
                        "query_type": parsed.query_type.unwrap_or_else(|| "".to_string()),
                        "server_ip": server_ip,
                        "server_port": server_port
                    }
                })
                .to_string(),
            )
        }
        EVENT_DNS_RESPONSE => {
            let payload = dns_payload(event);
            let (dns_bytes, mut transport) = dns_payload_view(&payload);
            let parsed = parse_dns(dns_bytes);
            let socket = socket_info(pid, event.fd);
            if transport == "udp" {
                if let Some(info) = socket.as_ref() {
                    if info.protocol == "tcp" {
                        transport = "tcp";
                    }
                }
            }
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
                        "transport": transport,
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
            let sock_type = unix_socket_type(pid, event.fd).unwrap_or("unknown");
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
                        "sock_type": sock_type
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

fn is_zero_ip(ip: &str) -> bool {
    ip == "0.0.0.0" || ip == "::"
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

struct SocketInfo {
    family: u16,
    protocol: &'static str,
    local_ip: String,
    local_port: u16,
    remote_ip: String,
    remote_port: u16,
}

fn socket_info(pid: u32, fd: i32) -> Option<SocketInfo> {
    let inode = socket_inode(pid, fd)?;
    find_inet_socket(pid, inode)
}

fn socket_inode(pid: u32, fd: i32) -> Option<u64> {
    if fd < 0 {
        return None;
    }
    let link = fs::read_link(format!("/proc/{pid}/fd/{fd}")).ok()?;
    let link_str = link.to_string_lossy();
    let inode_str = link_str.strip_prefix("socket:[")?.strip_suffix(']')?;
    inode_str.parse::<u64>().ok()
}

fn find_inet_socket(pid: u32, inode: u64) -> Option<SocketInfo> {
    let candidates = [
        ("tcp", AF_INET, "tcp"),
        ("udp", AF_INET, "udp"),
        ("tcp6", AF_INET6, "tcp"),
        ("udp6", AF_INET6, "udp"),
    ];
    for (net_file, family, protocol) in candidates {
        let path = format!("/proc/{pid}/net/{net_file}");
        if let Some(info) = parse_proc_net(&path, family, protocol, inode) {
            return Some(info);
        }
    }
    None
}

fn parse_proc_net(
    path: &str,
    family: u16,
    protocol: &'static str,
    inode: u64,
) -> Option<SocketInfo> {
    let content = fs::read_to_string(path).ok()?;
    for line in content.lines().skip(1) {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 10 {
            continue;
        }
        let inode_str = parts[9];
        let entry_inode = inode_str.parse::<u64>().ok()?;
        if entry_inode != inode {
            continue;
        }
        let (local_addr, local_port) = split_addr_port(parts[1])?;
        let (remote_addr, remote_port) = split_addr_port(parts[2])?;
        let local_ip = parse_addr(family, local_addr)?;
        let remote_ip = parse_addr(family, remote_addr)?;
        let local_port = u16::from_str_radix(local_port, 16).ok()?;
        let remote_port = u16::from_str_radix(remote_port, 16).ok()?;
        return Some(SocketInfo {
            family,
            protocol,
            local_ip,
            local_port,
            remote_ip,
            remote_port,
        });
    }
    None
}

fn split_addr_port(addr: &str) -> Option<(&str, &str)> {
    let mut parts = addr.split(':');
    let host = parts.next()?;
    let port = parts.next()?;
    Some((host, port))
}

fn parse_addr(family: u16, addr: &str) -> Option<String> {
    match family {
        AF_INET => Some(parse_ipv4_hex(addr)?.to_string()),
        AF_INET6 => Some(parse_ipv6_hex(addr)?.to_string()),
        _ => None,
    }
}

fn parse_ipv4_hex(hex: &str) -> Option<Ipv4Addr> {
    if hex.len() != 8 {
        return None;
    }
    let value = u32::from_str_radix(hex, 16).ok()?;
    let bytes = value.to_le_bytes();
    Some(Ipv4Addr::new(bytes[0], bytes[1], bytes[2], bytes[3]))
}

fn parse_ipv6_hex(hex: &str) -> Option<Ipv6Addr> {
    if hex.len() != 32 {
        return None;
    }
    let mut bytes = [0u8; 16];
    for i in 0..16 {
        let start = i * 2;
        let end = start + 2;
        bytes[i] = u8::from_str_radix(&hex[start..end], 16).ok()?;
    }
    for chunk in bytes.chunks_exact_mut(4) {
        chunk.reverse();
    }
    Some(Ipv6Addr::from(bytes))
}

fn unix_socket_type(pid: u32, fd: i32) -> Option<&'static str> {
    let inode = socket_inode(pid, fd)?;
    parse_proc_net_unix(pid, inode)
}

fn parse_proc_net_unix(pid: u32, inode: u64) -> Option<&'static str> {
    let content = fs::read_to_string(format!("/proc/{pid}/net/unix")).ok()?;
    for line in content.lines().skip(1) {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 7 {
            continue;
        }
        let entry_inode = parts[6].parse::<u64>().ok()?;
        if entry_inode != inode {
            continue;
        }
        let socket_type = u32::from_str_radix(parts[4], 16).ok()?;
        return Some(unix_type_to_string(socket_type));
    }
    None
}

fn unix_type_to_string(socket_type: u32) -> &'static str {
    match socket_type {
        1 => "stream",
        2 => "dgram",
        3 => "raw",
        4 => "rdm",
        5 => "seqpacket",
        _ => "unknown",
    }
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

fn dns_payload_view(payload: &[u8]) -> (&[u8], &'static str) {
    if payload.len() >= 2 {
        let tcp_len = u16::from_be_bytes([payload[0], payload[1]]) as usize;
        if tcp_len >= 12 && tcp_len <= payload.len().saturating_sub(2) {
            return (&payload[2..2 + tcp_len], "tcp");
        }
    }
    (payload, "udp")
}

fn dns_server_info(
    event: &Event,
    socket: Option<&SocketInfo>,
    is_query: bool,
) -> (String, u16) {
    let (mut ip, mut port) = if is_query {
        (
            addr_to_string(event.family as u16, &event.dst_addr),
            event.dst_port,
        )
    } else {
        (
            addr_to_string(event.family as u16, &event.src_addr),
            event.src_port,
        )
    };

    if is_zero_ip(&ip) {
        ip.clear();
    }

    if (ip.is_empty() || port == 0) && socket.is_some() {
        let socket = socket.unwrap();
        ip = socket.remote_ip.clone();
        port = socket.remote_port;
    }

    (ip, port)
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
