"""Private integrity records, independent of project receipts and configuration."""
import ctypes
import json
import os
from pathlib import Path
import stat

from .files import _reject_links, resolve_owned, write_receipt


def _windows_security(path, *, create=False, strict=True):
    from ctypes import wintypes as w
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    ptr = ctypes.c_void_p
    adv.OpenProcessToken.argtypes = (w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE))
    adv.GetTokenInformation.argtypes = (w.HANDLE, ctypes.c_int, ptr, w.DWORD, ctypes.POINTER(w.DWORD))
    adv.ConvertSidToStringSidW.argtypes = (ptr, ctypes.POINTER(w.LPWSTR))
    adv.LookupAccountNameW.argtypes = (w.LPCWSTR, w.LPCWSTR, ptr, ctypes.POINTER(w.DWORD), w.LPWSTR, ctypes.POINTER(w.DWORD), ctypes.POINTER(w.DWORD))
    adv.GetNamedSecurityInfoW.argtypes = (w.LPWSTR, ctypes.c_int, w.DWORD, ctypes.POINTER(ptr), ptr, ctypes.POINTER(ptr), ptr, ctypes.POINTER(ptr))
    adv.GetNamedSecurityInfoW.restype = w.DWORD
    adv.GetAce.argtypes = (ptr, w.DWORD, ctypes.POINTER(ptr))
    adv.GetAclInformation.argtypes = (ptr, ptr, w.DWORD, ctypes.c_int)
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (w.LPCWSTR, w.DWORD, ctypes.POINTER(ptr), ptr)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = (w.HANDLE,)
    kernel.LocalFree.argtypes = (ptr,)
    kernel.LocalFree.restype = ptr
    kernel.CreateDirectoryW.argtypes = (w.LPCWSTR, ptr)

    def sid_text(sid):
        text = w.LPWSTR()
        if not adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise OSError('cannot inspect Windows identity')
        try:
            return text.value
        finally:
            kernel.LocalFree(ctypes.cast(text, ptr))

    token = w.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise OSError('cannot inspect Windows token')
    try:
        size = w.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
            raise OSError('cannot inspect Windows token user')
        user = sid_text(ctypes.cast(buffer, ctypes.POINTER(ptr))[0])
    finally:
        kernel.CloseHandle(token)
    trusted = {user, 'S-1-5-18', 'S-1-5-32-544'}
    if not strict:
        sid_size, domain_size, use = w.DWORD(), w.DWORD(), w.DWORD()
        adv.LookupAccountNameW(None, 'NT SERVICE\\TrustedInstaller', None, ctypes.byref(sid_size), None, ctypes.byref(domain_size), ctypes.byref(use))
        sid_buffer = ctypes.create_string_buffer(sid_size.value)
        domain = ctypes.create_unicode_buffer(domain_size.value)
        if adv.LookupAccountNameW(None, 'NT SERVICE\\TrustedInstaller', sid_buffer, ctypes.byref(sid_size), domain, ctypes.byref(domain_size), ctypes.byref(use)):
            trusted.add(sid_text(sid_buffer))
    if create:
        descriptor = ptr()
        sddl = f'O:{user}D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;{user})'
        if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
            raise OSError('cannot create private security descriptor')
        class Attributes(ctypes.Structure):
            _fields_ = [('length', w.DWORD), ('descriptor', ptr), ('inherit', w.BOOL)]
        attributes = Attributes(ctypes.sizeof(Attributes), descriptor, False)
        try:
            if not kernel.CreateDirectoryW(str(path), ctypes.byref(attributes)):
                raise OSError('cannot create private state directory')
        finally:
            kernel.LocalFree(descriptor)
    owner, dacl, descriptor = ptr(), ptr(), ptr()
    if adv.GetNamedSecurityInfoW(str(path), 1, 5, ctypes.byref(owner), None, ctypes.byref(dacl), None, ctypes.byref(descriptor)):
        raise OSError('cannot inspect private state ACL')
    try:
        if not owner or sid_text(owner) not in ({user} if strict else trusted) or not dacl:
            raise ValueError('unsafe private state owner or ACL')
        class AclSize(ctypes.Structure):
            _fields_ = [('count', w.DWORD), ('used', w.DWORD), ('free', w.DWORD)]
        info = AclSize()
        if not adv.GetAclInformation(dacl, ctypes.byref(info), ctypes.sizeof(info), 2):
            raise OSError('cannot inspect private ACL entries')
        dangerous = 0x10000000 | 0x40000000 | 0x10000 | 0x40000 | 0x80000 | 0x40
        if strict:
            dangerous |= 0x116
        for index in range(info.count):
            ace = ptr()
            if not adv.GetAce(dacl, index, ctypes.byref(ace)):
                raise OSError('cannot inspect private ACL entry')
            header = ctypes.string_at(ace, 8)
            kind, flags = header[0], header[1]
            if flags & 8:
                continue  # Inherit-only ACE does not grant access to this ancestor.
            if kind == 1:
                continue
            if kind != 0:
                raise ValueError('unsupported private state ACL entry')
            mask = int.from_bytes(header[4:8], 'little')
            if mask & dangerous and sid_text(ace.value + 8) not in trusted:
                raise ValueError('private state is writable by another identity')
    finally:
        kernel.LocalFree(descriptor)


def secure(path, *, create=False, strict=True):
    path = Path(path)
    _reject_links(path)
    if path.name:
        resolve_owned(path.parent, path.name)
    if os.name == 'nt':
        _windows_security(path, create=create, strict=strict)
    elif os.name == 'posix':
        if create:
            path.mkdir(mode=0o700)
        metadata = path.stat()
        if metadata.st_uid not in ({os.getuid()} if strict else {os.getuid(), 0}):
            raise ValueError('unsafe private state owner')
        if metadata.st_mode & 0o022 and not (not strict and metadata.st_mode & stat.S_ISVTX):
            raise ValueError('unsafe private state permissions')
        if strict and metadata.st_mode & 0o077:
            raise ValueError('private state is accessible by another identity')
    else:
        raise ValueError('private state permissions unsupported on this platform')
    if path.is_file() and path.stat().st_nlink != 1:
        raise ValueError('private state hardlink rejected')


def store(base, root, scope):
    base, root = Path(os.path.abspath(base)), Path(os.path.abspath(root))
    resolve_owned(base.parent, base.name)
    if base == root or root.is_relative_to(base) or (scope == 'project' and base.is_relative_to(root)) or base.is_relative_to(root / '.agentic-sdlc'):
        raise ValueError('private state overlaps project or runtime tree')
    for ancestor in reversed(base.parents):
        secure(ancestor, strict=False)
    secure(base, create=not base.exists())
    return base


def read(base, name):
    path = resolve_owned(base, name)
    if not path.exists():
        return None
    secure(path)
    return json.loads(path.read_text(encoding='utf-8'))


def write(base, name, value):
    path = resolve_owned(base, name)
    if path.exists():
        secure(path)
    write_receipt(path, value)
    if os.name == 'posix':
        path.chmod(0o600)
    secure(path)
