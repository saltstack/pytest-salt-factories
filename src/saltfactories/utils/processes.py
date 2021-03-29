"""
saltfactories.utils.processes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Process related utilities
"""
import errno
import logging
import pprint
import signal
import weakref

import attr
import psutil


log = logging.getLogger(__name__)


@attr.s(frozen=True)
class ProcessResult:
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    exitcode = attr.ib()
    stdout = attr.ib()
    stderr = attr.ib()
    cmdline = attr.ib(default=None, kw_only=True)

    @exitcode.validator
    def _validate_exitcode(self, attribute, value):
        if not isinstance(value, int):
            raise ValueError("'exitcode' needs to be an integer, not '{}'".format(type(value)))

    def __str__(self):
        message = self.__class__.__name__
        if self.cmdline:
            message += "\n Command Line: {}".format(self.cmdline)
        if self.exitcode is not None:
            message += "\n Exitcode: {}".format(self.exitcode)
        if self.stdout or self.stderr:
            message += "\n Process Output:"
        if self.stdout:
            message += "\n   >>>>> STDOUT >>>>>\n{}\n   <<<<< STDOUT <<<<<".format(self.stdout)
        if self.stderr:
            message += "\n   >>>>> STDERR >>>>>\n{}\n   <<<<< STDERR <<<<<".format(self.stderr)
        return message + "\n"


@attr.s(frozen=True)
class ShellResult(ProcessResult):
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    json = attr.ib(default=None, kw_only=True)

    def __str__(self):
        message = super().__str__().rstrip()
        if self.json:
            message += "\n JSON Object:\n"
            message += "".join("  {}".format(line) for line in pprint.pformat(self.json))
        return message + "\n"

    def __eq__(self, other):
        """
        Allow comparison against the parsed JSON or the output
        """
        if self.json:
            return self.json == other
        return self.stdout == other


def collect_child_processes(pid):
    """
    Try to collect any started child processes of the provided pid
    """
    # Let's get the child processes of the started subprocess
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    return children


def _get_cmdline(proc):
    # pylint: disable=protected-access
    try:
        return proc._cmdline
    except AttributeError:
        # Cache the cmdline since that will be inaccessible once the process is terminated
        # and we use it in log calls
        try:
            cmdline = proc.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # OSX is more restrictive about the above information
            cmdline = None
        except OSError:
            # On Windows we've seen something like:
            #   File " c: ... \lib\site-packages\pytestsalt\utils\__init__.py", line 182, in terminate_process
            #     terminate_process_list(process_list, kill=slow_stop is False, slow_stop=slow_stop)
            #   File " c: ... \lib\site-packages\pytestsalt\utils\__init__.py", line 130, in terminate_process_list
            #     _terminate_process_list(process_list, kill=kill, slow_stop=slow_stop)
            #   File " c: ... \lib\site-packages\pytestsalt\utils\__init__.py", line 78, in _terminate_process_list
            #     cmdline = process.cmdline()
            #   File " c: ... \lib\site-packages\psutil\__init__.py", line 786, in cmdline
            #     return self._proc.cmdline()
            #   File " c: ... \lib\site-packages\psutil\_pswindows.py", line 667, in wrapper
            #     return fun(self, *args, **kwargs)
            #   File " c: ... \lib\site-packages\psutil\_pswindows.py", line 745, in cmdline
            #     ret = cext.proc_cmdline(self.pid, use_peb=True)
            #   OSError: [WinError 299] Only part of a ReadProcessMemory or WriteProcessMemory request was completed: 'originated from ReadProcessMemory(ProcessParameters)
            cmdline = None
        except RuntimeError:
            # Also on windows
            # saltfactories\utils\processes\helpers.py:68: in _get_cmdline
            #     cmdline = proc.as_dict()
            # c: ... \lib\site-packages\psutil\__init__.py:634: in as_dict
            #     ret = meth()
            # c: ... \lib\site-packages\psutil\__init__.py:1186: in memory_full_info
            #     return self._proc.memory_full_info()
            # c: ... \lib\site-packages\psutil\_pswindows.py:667: in wrapper
            #     return fun(self, *args, **kwargs)
            # _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
            #
            # self = <psutil._pswindows.Process object at 0x0000029B7FDA5558>
            #
            #     @wrap_exceptions
            #     def memory_full_info(self):
            #         basic_mem = self.memory_info()
            # >       uss = cext.proc_memory_uss(self.pid)
            # E       RuntimeError: NtQueryVirtualMemory failed
            #
            # c: ... \lib\site-packages\psutil\_pswindows.py:806: RuntimeError
            cmdline = None

        if not cmdline:
            try:
                cmdline = proc.as_dict()
            except psutil.NoSuchProcess:
                cmdline = "<could not be retrived; dead process: {}>".format(proc)
            except (psutil.AccessDenied, OSError):
                cmdline = weakref.proxy(proc)
        proc._cmdline = cmdline
    return proc._cmdline
    # pylint: enable=protected-access


def _terminate_process_list(process_list, kill=False, slow_stop=False):
    log.info(
        "Terminating process list:\n%s",
        pprint.pformat([_get_cmdline(proc) for proc in process_list]),
    )
    for process in process_list[:]:  # Iterate over copy of the list
        if not psutil.pid_exists(process.pid):
            process_list.remove(process)
            continue
        try:
            if not kill and process.status() == psutil.STATUS_ZOMBIE:
                # Zombie processes will exit once child processes also exit
                continue
            if kill:
                log.info("Killing process(%s): %s", process.pid, _get_cmdline(process))
                process.kill()
            else:
                log.info("Terminating process(%s): %s", process.pid, _get_cmdline(process))
                try:
                    if slow_stop:
                        # Allow coverage data to be written down to disk
                        process.send_signal(signal.SIGTERM)
                        try:
                            process.wait(2)
                        except psutil.TimeoutExpired:
                            if psutil.pid_exists(process.pid):
                                continue
                    else:
                        process.terminate()
                except OSError as exc:
                    if exc.errno not in (errno.ESRCH, errno.EACCES):
                        raise
            if not psutil.pid_exists(process.pid):
                process_list.remove(process)
        except psutil.NoSuchProcess:
            process_list.remove(process)


def terminate_process_list(process_list, kill=False, slow_stop=False):
    def on_process_terminated(proc):
        log.info(
            "Process %s terminated with exit code: %s",
            getattr(proc, "_cmdline", proc),
            proc.returncode,
        )

    # Try to terminate processes with the provided kill and slow_stop parameters
    log.info("Terminating process list. 1st step. kill: %s, slow stop: %s", kill, slow_stop)

    # Remove duplicates from the process list
    seen_pids = []
    start_count = len(process_list)
    for proc in process_list[:]:
        if proc.pid in seen_pids:
            process_list.remove(proc)
        seen_pids.append(proc.pid)
    end_count = len(process_list)
    if end_count < start_count:
        log.debug("Removed %d duplicates from the initial process list", start_count - end_count)

    _terminate_process_list(process_list, kill=kill, slow_stop=slow_stop)
    psutil.wait_procs(process_list, timeout=5, callback=on_process_terminated)

    if process_list:
        # If there's still processes to be terminated, retry and kill them if slow_stop is False
        log.info(
            "Terminating process list. 2nd step. kill: %s, slow stop: %s",
            slow_stop is False,
            slow_stop,
        )
        _terminate_process_list(process_list, kill=slow_stop is False, slow_stop=slow_stop)
        psutil.wait_procs(process_list, timeout=5, callback=on_process_terminated)

    if process_list:
        # If there's still processes to be terminated, just kill them, no slow stopping now
        log.info("Terminating process list. 3rd step. kill: True, slow stop: False")
        _terminate_process_list(process_list, kill=True, slow_stop=False)
        psutil.wait_procs(process_list, timeout=5, callback=on_process_terminated)

    if process_list:
        # In there's still processes to be terminated, log a warning about it
        log.warning("Some processes failed to properly terminate: %s", process_list)


def terminate_process(pid=None, process=None, children=None, kill_children=None, slow_stop=False):
    """
    Try to terminate/kill the started process
    """
    children = children or []
    process_list = []

    if kill_children is None:
        # Always kill children if kill the parent process and kill_children was not set
        kill_children = True if slow_stop is False else kill_children

    if pid and not process:
        try:
            process = psutil.Process(pid)
            process_list.append(process)
        except psutil.NoSuchProcess:
            # Process is already gone
            process = None

    if kill_children:
        if process:
            children.extend(collect_child_processes(pid))
        if children:
            process_list.extend(children)

    if process_list:
        if process:
            log.info("Stopping process %s and respective children: %s", process, children)
        else:
            log.info("Terminating process list: %s", process_list)
        terminate_process_list(process_list, kill=slow_stop is False, slow_stop=slow_stop)
