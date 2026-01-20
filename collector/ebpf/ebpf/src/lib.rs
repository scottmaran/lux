#![no_std]
#![no_main]

use aya_bpf::{
    helpers::{
        bpf_get_current_cgroup_id, bpf_get_current_comm, bpf_get_current_pid_tgid,
        bpf_get_current_uid_gid, bpf_ktime_get_ns, bpf_probe_read_user,
        bpf_probe_read_user_buf,
    },
    macros::{map, tracepoint},
    maps::{HashMap, PerCpuArray, RingBuf},
    programs::TracePointContext,
};
use core::{mem, ptr};

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
pub struct Event {
    pub event_type: u8,
    pub family: u8,
    pub protocol: u8,
    pub _pad: u8,
    pub pid: u32,
    pub uid: u32,
    pub gid: u32,
    pub cgroup_id: u64,
    pub ts: u64,
    pub syscall_result: i64,
    pub src_addr: [u8; 16],
    pub dst_addr: [u8; 16],
    pub src_port: u16,
    pub dst_port: u16,
    pub bytes: u32,
    pub comm: [u8; TASK_COMM_LEN],
    pub unix_path_len: u16,
    pub unix_path: [u8; UNIX_PATH_MAX],
    pub dns_payload_len: u16,
    pub dns_payload: [u8; DNS_PAYLOAD_MAX],
}

#[repr(C)]
#[derive(Copy, Clone)]
struct ConnectArgs {
    family: u16,
    port: u16,
    addr: [u8; 16],
    unix_path_len: u16,
    unix_path: [u8; UNIX_PATH_MAX],
}

#[repr(C)]
#[derive(Copy, Clone)]
struct SendArgs {
    family: u16,
    port: u16,
    addr: [u8; 16],
    buf: u64,
    len: u32,
}

#[repr(C)]
#[derive(Copy, Clone)]
struct RecvArgs {
    buf: u64,
    len: u32,
    addr_ptr: u64,
    addrlen: u32,
}

#[repr(C)]
struct TracepointCommon {
    _type: u16,
    _flags: u8,
    _preempt_count: u8,
    _pid: i32,
}

#[repr(C)]
struct SysEnterArgs {
    _common: TracepointCommon,
    _id: i64,
    args: [u64; 6],
}

#[repr(C)]
struct SysExitArgs {
    _common: TracepointCommon,
    _id: i64,
    ret: i64,
}

#[repr(C)]
struct SockAddrIn {
    sin_family: u16,
    sin_port: u16,
    sin_addr: u32,
    _zero: [u8; 8],
}

#[repr(C)]
struct SockAddrIn6 {
    sin6_family: u16,
    sin6_port: u16,
    _flowinfo: u32,
    sin6_addr: [u8; 16],
    _scope_id: u32,
}

#[repr(C)]
struct SockAddrUn {
    sun_family: u16,
    sun_path: [u8; UNIX_PATH_MAX],
}

#[map(name = "CONNECT_ARGS")]
static mut CONNECT_ARGS: HashMap<u32, ConnectArgs> = HashMap::with_max_entries(1024, 0);

#[map(name = "SEND_ARGS")]
static mut SEND_ARGS: HashMap<u32, SendArgs> = HashMap::with_max_entries(4096, 0);

#[map(name = "RECV_ARGS")]
static mut RECV_ARGS: HashMap<u32, RecvArgs> = HashMap::with_max_entries(4096, 0);

#[map(name = "EVENTS")]
static mut EVENTS: RingBuf = RingBuf::with_byte_size(1 << 24, 0);

#[map(name = "EVENT_BUF")]
static mut EVENT_BUF: PerCpuArray<Event> = PerCpuArray::with_max_entries(1, 0);

fn now_ns() -> u64 {
    unsafe { bpf_ktime_get_ns() }
}

fn current_pid() -> u32 {
    (bpf_get_current_pid_tgid() >> 32) as u32
}

fn current_uid_gid() -> (u32, u32) {
    let uid_gid = bpf_get_current_uid_gid();
    (uid_gid as u32, (uid_gid >> 32) as u32)
}

fn fill_common(event: &mut Event) {
    event.ts = now_ns();
    event.pid = current_pid();
    let (uid, gid) = current_uid_gid();
    event.uid = uid;
    event.gid = gid;
    event.cgroup_id = unsafe { bpf_get_current_cgroup_id() };
    if let Ok(comm) = bpf_get_current_comm() {
        event.comm = comm;
    }
}

fn init_event(event: &mut Event) {
    unsafe {
        ptr::write_bytes(
            event as *mut Event as *mut u8,
            0,
            mem::size_of::<Event>(),
        );
    }
}

fn emit(event: &Event) {
    unsafe {
        let _ = EVENTS.output(event, 0);
    }
}

fn with_event<F>(mut f: F)
where
    F: FnOnce(&mut Event) -> bool,
{
    unsafe {
        if let Some(ptr) = EVENT_BUF.get_ptr_mut(0) {
            let event = &mut *ptr;
            init_event(event);
            if f(event) {
                emit(event);
            }
        }
    }
}

fn parse_sockaddr(uservaddr: u64, addrlen: u32, out: &mut ConnectArgs) -> bool {
    if uservaddr == 0 {
        return false;
    }

    let family = match unsafe { bpf_probe_read_user(uservaddr as *const u16) } {
        Ok(value) => value,
        Err(_) => return false,
    };

    if family == AF_INET {
        if addrlen < mem::size_of::<SockAddrIn>() as u32 {
            return false;
        }
        let addr: SockAddrIn = match unsafe { bpf_probe_read_user(uservaddr as *const SockAddrIn) } {
            Ok(value) => value,
            Err(_) => return false,
        };
        out.family = AF_INET;
        out.port = u16::from_be(addr.sin_port);
        out.addr = [0u8; 16];
        out.addr[..4].copy_from_slice(&u32::from_be(addr.sin_addr).to_be_bytes());
        return true;
    }

    if family == AF_INET6 {
        if addrlen < mem::size_of::<SockAddrIn6>() as u32 {
            return false;
        }
        let addr: SockAddrIn6 =
            match unsafe { bpf_probe_read_user(uservaddr as *const SockAddrIn6) } {
                Ok(value) => value,
                Err(_) => return false,
            };
        out.family = AF_INET6;
        out.port = u16::from_be(addr.sin6_port);
        out.addr = addr.sin6_addr;
        return true;
    }

    if family == AF_UNIX {
        let addr: SockAddrUn = match unsafe { bpf_probe_read_user(uservaddr as *const SockAddrUn) }
        {
            Ok(value) => value,
            Err(_) => return false,
        };
        out.family = AF_UNIX;
        out.unix_path = addr.sun_path;
        out.unix_path_len = unix_path_len(&addr.sun_path);
        return true;
    }

    false
}

fn unix_path_len(path: &[u8; UNIX_PATH_MAX]) -> u16 {
    let mut len = 0u16;
    let mut i = if path[0] == 0 { 1 } else { 0 };
    while i < UNIX_PATH_MAX {
        if path[i] == 0 {
            break;
        }
        len += 1;
        i += 1;
    }
    len
}

#[tracepoint(category = "syscalls", name = "sys_enter_connect")]
pub fn sys_enter_connect(ctx: TracePointContext) -> u32 {
    match try_sys_enter_connect(ctx) {
        Ok(_) => 0,
        Err(_) => 0,
    }
}

fn try_sys_enter_connect(ctx: TracePointContext) -> Result<(), i64> {
    let args: SysEnterArgs = unsafe { ctx.read_at(0)? };
    let uservaddr = args.args[1];
    let addrlen = args.args[2] as u32;

    let mut parsed: ConnectArgs = unsafe { mem::zeroed() };
    if !parse_sockaddr(uservaddr, addrlen, &mut parsed) {
        return Ok(());
    }

    let pid = current_pid();
    unsafe {
        CONNECT_ARGS.insert(&pid, &parsed, 0)?;
    }
    Ok(())
}

#[tracepoint(category = "syscalls", name = "sys_exit_connect")]
pub fn sys_exit_connect(ctx: TracePointContext) -> u32 {
    match try_sys_exit_connect(ctx) {
        Ok(_) => 0,
        Err(_) => 0,
    }
}

fn try_sys_exit_connect(ctx: TracePointContext) -> Result<(), i64> {
    let args: SysExitArgs = unsafe { ctx.read_at(0)? };
    let ret = args.ret;
    let pid = current_pid();

    let parsed = unsafe { CONNECT_ARGS.get(&pid) };
    let parsed = match parsed {
        Some(value) => *value,
        None => return Ok(()),
    };
    let _ = unsafe { CONNECT_ARGS.remove(&pid) };

    if parsed.family == AF_UNIX {
        with_event(|event| {
            fill_common(event);
            event.syscall_result = ret;
            event.event_type = EVENT_UNIX_CONNECT;
            event.family = AF_UNIX as u8;
            event.unix_path_len = parsed.unix_path_len;
            event.unix_path = parsed.unix_path;
            true
        });
        return Ok(());
    }

    with_event(|event| {
        fill_common(event);
        event.syscall_result = ret;
        event.event_type = EVENT_NET_CONNECT;
        event.family = parsed.family as u8;
        event.protocol = IPPROTO_TCP;
        event.dst_addr = parsed.addr;
        event.dst_port = parsed.port;
        true
    });

    Ok(())
}

#[tracepoint(category = "syscalls", name = "sys_enter_sendto")]
pub fn sys_enter_sendto(ctx: TracePointContext) -> u32 {
    match try_sys_enter_sendto(ctx) {
        Ok(_) => 0,
        Err(_) => 0,
    }
}

fn try_sys_enter_sendto(ctx: TracePointContext) -> Result<(), i64> {
    let args: SysEnterArgs = unsafe { ctx.read_at(0)? };
    let buf = args.args[1];
    let len = args.args[2] as u32;
    let dest_addr = args.args[4];
    let addrlen = args.args[5] as u32;

    let mut parsed: ConnectArgs = unsafe { mem::zeroed() };
    if !parse_sockaddr(dest_addr, addrlen, &mut parsed) {
        return Ok(());
    }

    if parsed.family != AF_INET && parsed.family != AF_INET6 {
        return Ok(());
    }

    let send_args = SendArgs {
        family: parsed.family,
        port: parsed.port,
        addr: parsed.addr,
        buf,
        len,
    };

    let pid = current_pid();
    unsafe {
        SEND_ARGS.insert(&pid, &send_args, 0)?;
    }

    Ok(())
}

#[tracepoint(category = "syscalls", name = "sys_exit_sendto")]
pub fn sys_exit_sendto(ctx: TracePointContext) -> u32 {
    match try_sys_exit_sendto(ctx) {
        Ok(_) => 0,
        Err(_) => 0,
    }
}

fn try_sys_exit_sendto(ctx: TracePointContext) -> Result<(), i64> {
    let args: SysExitArgs = unsafe { ctx.read_at(0)? };
    let ret = args.ret;
    let pid = current_pid();

    let stored = unsafe { SEND_ARGS.get(&pid) };
    let stored = match stored {
        Some(value) => *value,
        None => return Ok(()),
    };
    let _ = unsafe { SEND_ARGS.remove(&pid) };

    with_event(|event| {
        fill_common(event);
        event.event_type = EVENT_NET_SEND;
        event.family = stored.family as u8;
        event.protocol = IPPROTO_UDP;
        event.dst_addr = stored.addr;
        event.dst_port = stored.port;
        event.bytes = if ret > 0 { ret as u32 } else { 0 };
        event.syscall_result = ret;
        true
    });

    if stored.port == 53 {
        with_event(|event| {
            fill_common(event);
            event.event_type = EVENT_DNS_QUERY;
            event.family = stored.family as u8;
            event.protocol = IPPROTO_UDP;
            event.dst_addr = stored.addr;
            event.dst_port = stored.port;
            event.syscall_result = if ret >= 0 { 0 } else { ret };

            let mut payload_len = stored.len;
            if payload_len > DNS_PAYLOAD_MAX as u32 {
                payload_len = DNS_PAYLOAD_MAX as u32;
            }
            event.dns_payload_len = payload_len as u16;
            if payload_len > 0 {
                let dst = &mut event.dns_payload[..payload_len as usize];
                unsafe {
                    let _ = bpf_probe_read_user_buf(stored.buf as *const u8, dst);
                }
            }
            true
        });
    }

    Ok(())
}

#[tracepoint(category = "syscalls", name = "sys_enter_recvfrom")]
pub fn sys_enter_recvfrom(ctx: TracePointContext) -> u32 {
    match try_sys_enter_recvfrom(ctx) {
        Ok(_) => 0,
        Err(_) => 0,
    }
}

fn try_sys_enter_recvfrom(ctx: TracePointContext) -> Result<(), i64> {
    let args: SysEnterArgs = unsafe { ctx.read_at(0)? };
    let buf = args.args[1];
    let len = args.args[2] as u32;
    let recv_args = RecvArgs {
        buf,
        len,
        addr_ptr: args.args[4],
        addrlen: args.args[5] as u32,
    };

    let pid = current_pid();
    unsafe {
        RECV_ARGS.insert(&pid, &recv_args, 0)?;
    }

    Ok(())
}

#[tracepoint(category = "syscalls", name = "sys_exit_recvfrom")]
pub fn sys_exit_recvfrom(ctx: TracePointContext) -> u32 {
    match try_sys_exit_recvfrom(ctx) {
        Ok(_) => 0,
        Err(_) => 0,
    }
}

fn try_sys_exit_recvfrom(ctx: TracePointContext) -> Result<(), i64> {
    let args: SysExitArgs = unsafe { ctx.read_at(0)? };
    let ret = args.ret;
    if ret <= 0 {
        return Ok(());
    }

    let pid = current_pid();
    let stored = unsafe { RECV_ARGS.get(&pid) };
    let stored = match stored {
        Some(value) => *value,
        None => return Ok(()),
    };
    let _ = unsafe { RECV_ARGS.remove(&pid) };

    let mut parsed: ConnectArgs = unsafe { mem::zeroed() };
    if !parse_sockaddr(stored.addr_ptr, stored.addrlen, &mut parsed) {
        return Ok(());
    }
    if parsed.family != AF_INET && parsed.family != AF_INET6 {
        return Ok(());
    }
    if parsed.port != 53 {
        return Ok(());
    }

    with_event(|event| {
        fill_common(event);
        event.event_type = EVENT_DNS_RESPONSE;
        event.family = parsed.family as u8;
        event.protocol = IPPROTO_UDP;
        event.src_addr = parsed.addr;
        event.src_port = parsed.port;
        event.syscall_result = if ret >= 0 { 0 } else { ret };

        let mut payload_len = ret as u32;
        if payload_len > stored.len {
            payload_len = stored.len;
        }
        if payload_len > DNS_PAYLOAD_MAX as u32 {
            payload_len = DNS_PAYLOAD_MAX as u32;
        }
        event.dns_payload_len = payload_len as u16;
        if payload_len > 0 {
            let dst = &mut event.dns_payload[..payload_len as usize];
            unsafe {
                let _ = bpf_probe_read_user_buf(stored.buf as *const u8, dst);
            }
        }

        true
    });
    Ok(())
}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo) -> ! {
    unsafe { core::hint::unreachable_unchecked() }
}
