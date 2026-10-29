"""Windows process lifetime control; this does not restrict filesystem/network access."""
import os
from pathlib import Path
import subprocess
import threading
import time


def run(argv, *, cwd, env, timeout):
    """Create a Windows 10+ job atomically; fail closed without an uncontained fallback."""
    if (not argv or not all(isinstance(arg, str) and '\0' not in arg for arg in argv)
            or not Path(argv[0]).is_absolute() or Path(argv[0]).suffix.lower() != '.exe'):
        raise ValueError('absolute native executable required')
    if (not isinstance(env, dict) or any(not isinstance(k, str) or not k or '=' in k or '\0' in k
            or not isinstance(v, str) or '\0' in v for k, v in env.items())
            or '\0' in str(cwd) or timeout <= 0):
        raise ValueError('invalid process arguments')
    if os.name != 'nt':
        raise RuntimeError('Windows Job Object required')
    import ctypes as c
    from ctypes import wintypes as w
    import msvcrt

    class BasicLimits(c.Structure):
        _fields_ = [('process_time', c.c_longlong), ('job_time', c.c_longlong),
                    ('flags', w.DWORD), ('min_working', c.c_size_t), ('max_working', c.c_size_t),
                    ('active', w.DWORD), ('affinity', c.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]

    class Counters(c.Structure):
        _fields_ = [(name, c.c_ulonglong) for name in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]

    class Limits(c.Structure):
        _fields_ = [('basic', BasicLimits), ('io', Counters), ('process_memory', c.c_size_t),
                    ('job_memory', c.c_size_t), ('peak_process', c.c_size_t), ('peak_job', c.c_size_t)]

    class Startup(c.Structure):
        _fields_ = [('cb', w.DWORD), ('reserved', w.LPWSTR), ('desktop', w.LPWSTR), ('title', w.LPWSTR)] + [
            (name, w.DWORD) for name in ('x', 'y', 'width', 'height', 'x_chars', 'y_chars', 'fill', 'flags')] + [
            ('show', w.WORD), ('reserved_size', w.WORD), ('reserved_bytes', c.c_void_p),
            ('stdin', w.HANDLE), ('stdout', w.HANDLE), ('stderr', w.HANDLE)]

    class StartupEx(c.Structure):
        _fields_ = [('startup', Startup), ('attributes', c.c_void_p)]

    class ProcessInfo(c.Structure):
        _fields_ = [('process', w.HANDLE), ('thread', w.HANDLE), ('pid', w.DWORD), ('tid', w.DWORD)]

    api = c.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([c.c_void_p, w.LPCWSTR], w.HANDLE),
        'SetInformationJobObject': ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
        'InitializeProcThreadAttributeList': ([c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)], w.BOOL),
        'UpdateProcThreadAttribute': ([c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p], w.BOOL),
        'DeleteProcThreadAttributeList': ([c.c_void_p], None),
        'CreateProcessW': ([w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL, w.DWORD,
                            c.c_void_p, w.LPCWSTR, c.POINTER(StartupEx), c.POINTER(ProcessInfo)], w.BOOL),
        'TerminateJobObject': ([w.HANDLE, w.UINT], w.BOOL),
        'WaitForSingleObject': ([w.HANDLE, w.DWORD], w.DWORD),
        'GetExitCodeProcess': ([w.HANDLE, c.POINTER(w.DWORD)], w.BOOL),
        'CloseHandle': ([w.HANDLE], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = args, result

    def check(ok):
        if not ok:
            raise c.WinError(c.get_last_error())

    job = api.CreateJobObjectW(None, None)
    check(job)
    attributes = None
    info = ProcessInfo()
    descriptors = set()
    readers = []
    overflow = threading.Event()
    read_failed = threading.Event()
    buffers = [bytearray(), bytearray()]
    guard = threading.Lock()
    total = 0

    def kill():
        check(api.TerminateJobObject(job, 1))

    def drain(fd, buffer):
        nonlocal total
        try:
            while data := os.read(fd, 4096):
                with guard:
                    total += len(data)
                    buffer.extend(data[:max(0, 4096 - len(buffer))])
                    if total > 65536:
                        overflow.set()
                        api.TerminateJobObject(job, 1)
        except OSError:
            read_failed.set()
        finally:
            os.close(fd)

    try:
        limits = Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, no breakaway flags.
        check(api.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)))
        size = c.c_size_t()
        api.InitializeProcThreadAttributeList(None, 2, 0, c.byref(size))
        storage = c.create_string_buffer(size.value)
        check(api.InitializeProcThreadAttributeList(storage, 2, 0, c.byref(size)))
        attributes = storage
        out_read, out_write = os.pipe()
        descriptors.update((out_read, out_write))
        err_read, err_write = os.pipe()
        descriptors.update((err_read, err_write))
        stdin = os.open(os.devnull, os.O_RDONLY)
        descriptors.add(stdin)
        handles = (w.HANDLE * 3)(*[msvcrt.get_osfhandle(fd) for fd in (stdin, out_write, err_write)])
        for handle in handles:
            os.set_handle_inheritable(handle, True)
        jobs = (w.HANDLE * 1)(job)
        # Values from the Windows SDK ProcThreadAttributeValue macro (input attributes 2 and 13).
        check(api.UpdateProcThreadAttribute(storage, 0, 0x20002, handles, c.sizeof(handles), None, None))
        check(api.UpdateProcThreadAttribute(storage, 0, 0x2000D, jobs, c.sizeof(jobs), None, None))
        startup = StartupEx()
        startup.startup.cb = c.sizeof(startup)
        startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
        startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
        startup.attributes = c.cast(storage, c.c_void_p)
        command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
        environment = c.create_unicode_buffer('\0'.join(k + '=' + env[k] for k in sorted(env, key=str.upper)) + '\0\0')
        flags = 0x80000 | 0x400 | 0x08000000  # EXTENDED_STARTUPINFO_PRESENT | UNICODE_ENVIRONMENT | NO_WINDOW
        check(api.CreateProcessW(argv[0], command, None, None, True, flags, environment, str(cwd), c.byref(startup), c.byref(info)))
        for fd in (stdin, out_write, err_write):
            os.close(fd)
            descriptors.remove(fd)
        for fd, buffer in zip((out_read, err_read), buffers):
            reader = threading.Thread(target=drain, args=(fd, buffer), daemon=True)
            reader.start()
            descriptors.remove(fd)
            readers.append(reader)
        state = api.WaitForSingleObject(info.process, min(int(timeout * 1000), 0xFFFFFFFE))
        if state == 258:
            raise subprocess.TimeoutExpired(argv, timeout)
        if state != 0:
            raise c.WinError(c.get_last_error())
        code = w.DWORD()
        check(api.GetExitCodeProcess(info.process, c.byref(code)))
        kill()  # The parent may have exited while descendants still own output handles.
        deadline = time.monotonic() + 2
        for reader in readers:
            reader.join(max(0, deadline - time.monotonic()))
        if any(reader.is_alive() for reader in readers):
            raise RuntimeError('command output cleanup failed')
        if overflow.is_set():
            raise RuntimeError('command output limit exceeded')
        if read_failed.is_set():
            raise RuntimeError('command output capture failed')
        return subprocess.CompletedProcess(argv, code.value, *[bytes(data).decode('utf-8', errors='replace') for data in buffers])
    finally:
        if info.process:
            api.TerminateJobObject(job, 1)
            api.WaitForSingleObject(info.process, 2000)
        # Close the non-inherited job even if creation or waiting fails.
        api.CloseHandle(job)
        for reader in readers:
            reader.join(1)
        for handle in (info.thread, info.process):
            if handle:
                api.CloseHandle(handle)
        for fd in descriptors:
            os.close(fd)
        if attributes is not None:
            api.DeleteProcThreadAttributeList(attributes)
