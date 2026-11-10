# -*- coding: utf-8 -*-
"""Bounded retries for transient Windows sharing violations, never delete first."""
from __future__ import unicode_literals
import os,time

def retry(operation):
    for attempt in range(6):
        try:return operation()
        except OSError as exc:
            if os.name!='nt' or getattr(exc,'winerror',None) not in (5,32,33) or attempt==5:raise
            time.sleep(.025*(2**attempt))

def replace(source,target):
    def operation():
        if hasattr(os,'replace'):return os.replace(source,target)
        if os.name=='nt':
            import ctypes
            kernel=ctypes.windll.kernel32
            move=kernel.MoveFileExW;last=kernel.GetLastError
            if not move(type(u'')(source),type(u'')(target),9):raise ctypes.WinError(last())
        else:os.rename(source,target)
    return retry(operation)
