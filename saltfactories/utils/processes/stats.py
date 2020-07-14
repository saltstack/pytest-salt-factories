"""
saltfactories.utils.processes.stats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities to report statistics about the started subprocesses
"""
import sys

import psutil
import pytest
from _pytest.terminal import TerminalReporter

IS_WINDOWS = sys.platform.startswith("win")


class SaltTerminalReporter(TerminalReporter):
    def __init__(self, config):
        TerminalReporter.__init__(self, config)
        self._session = None
        self._show_sys_stats = config.getoption("--sys-stats") is True
        self._sys_stats_no_children = config.getoption("--sys-stats-no-children") is True
        if config.getoption("--sys-stats-uss-mem") is True:
            self._sys_stats_mem_type = "uss"
        else:
            self._sys_stats_mem_type = "rss"

    @pytest.hookimpl(trylast=True)
    def pytest_sessionstart(self, session):
        TerminalReporter.pytest_sessionstart(self, session)
        self._session = session

    def pytest_runtest_logreport(self, report):
        TerminalReporter.pytest_runtest_logreport(self, report)
        if self.verbosity <= 0:
            return

        if report.when != "call":
            return

        if self._show_sys_stats is False:
            return

        if self.verbosity > 1:
            remove_from_stats = set()
            self.ensure_newline()
            self.section("Processes Statistics", sep="-", bold=True)
            left_padding = len(max(["System"] + list(self._session.stats_processes), key=len))
            template = (
                "  ...{dots}  {name}  -  CPU: {cpu:6.2f} %   MEM: {mem:6.2f} % (Virtual Memory)"
            )

            stats = {
                "name": "System",
                "dots": "." * (left_padding - len("System")),
                "cpu": psutil.cpu_percent(),
                "mem": psutil.virtual_memory().percent,
            }

            swap = psutil.swap_memory().percent
            if swap > 0:
                template += "  SWAP: {swap:6.2f} %"
                stats["swap"] = swap

            template += "\n"
            self.write(template.format(**stats))

            template = "  ...{dots}  {name}  -  CPU: {cpu:6.2f} %   MEM: {mem:6.2f} % ({m_type})"
            children_template = (
                template + "   MEM SUM: {c_mem} % ({m_type})   CHILD PROCS: {c_count}\n"
            )
            no_children_template = template + "\n"
            for name, psproc in self._session.stats_processes.items():
                template = no_children_template
                dots = "." * (left_padding - len(name))
                pids = []
                try:
                    with psproc.oneshot():
                        stats = {
                            "name": name,
                            "dots": dots,
                            "cpu": psproc.cpu_percent(),
                            "mem": psproc.memory_percent(self._sys_stats_mem_type),
                            "m_type": self._sys_stats_mem_type.upper(),
                        }
                        if self._sys_stats_no_children is False:
                            pids.append(psproc.pid)
                            children = psproc.children(recursive=True)
                            if children:
                                template = children_template
                                stats["c_count"] = 0
                                c_mem = stats["mem"]
                                for child in children:
                                    if child.pid in pids:
                                        continue
                                    pids.append(child.pid)
                                    if not psutil.pid_exists(child.pid):
                                        continue
                                    try:
                                        c_mem += child.memory_percent(self._sys_stats_mem_type)
                                        stats["c_count"] += 1
                                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                                        continue
                                if stats["c_count"]:
                                    stats["c_mem"] = "{:6.2f}".format(c_mem)
                                else:
                                    template = no_children_template
                        self.write(template.format(**stats))
                except psutil.NoSuchProcess:
                    remove_from_stats.add(name)
                    continue
            if remove_from_stats:
                for name in remove_from_stats:
                    self._session.stats_processes.pop(name)

    def _get_progress_information_message(self):
        msg = TerminalReporter._get_progress_information_message(self)
        if self.verbosity <= 0:
            return msg
        if self.config.getoption("--sys-stats") is False:
            return msg
        if self.verbosity == 1:
            msg = " [CPU:{}%] [MEM:{}%]{}".format(
                psutil.cpu_percent(), psutil.virtual_memory().percent, msg
            )
        return msg
