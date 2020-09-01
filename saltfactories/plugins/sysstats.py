"""
    saltfactories.plugins.sysstats
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Process stats PyTest plugin interface
"""
import os
from collections import OrderedDict

import attr
import psutil
import pytest


@attr.s(kw_only=True, slots=True, hash=True)
class SystemStatsReporter:

    config = attr.ib(repr=False, hash=False)
    stats_processes = attr.ib(repr=False, hash=False)
    terminalreporter = attr.ib(repr=False, hash=False)
    show_sys_stats = attr.ib(init=False)
    sys_stats_no_children = attr.ib(init=False)
    sys_stats_mem_type = attr.ib(init=False)

    def __attrs_post_init__(self):
        self.show_sys_stats = self.config.getoption("--sys-stats") is True
        self.sys_stats_no_children = self.config.getoption("--sys-stats-no-children") is True
        if self.config.getoption("--sys-stats-uss-mem") is True:
            self.sys_stats_mem_type = "uss"
        else:
            self.sys_stats_mem_type = "rss"

    @pytest.hookimpl(trylast=True)
    def pytest_runtest_logreport(self, report):
        if self.terminalreporter.verbosity <= 0:
            return

        if report.when != "call":
            return

        if self.show_sys_stats is False:
            return

        if self.terminalreporter.verbosity > 1:
            remove_from_stats = set()
            self.terminalreporter.ensure_newline()
            self.terminalreporter.section("Processes Statistics", sep="-", bold=True)
            left_padding = len(max(["System"] + list(self.stats_processes), key=len))
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
            self.terminalreporter.write(template.format(**stats))

            template = "  ...{dots}  {name}  -  CPU: {cpu:6.2f} %   MEM: {mem:6.2f} % ({m_type})"
            children_template = (
                template + "   MEM SUM: {c_mem} % ({m_type})   CHILD PROCS: {c_count}\n"
            )
            no_children_template = template + "\n"
            for name, psproc in self.stats_processes.items():
                template = no_children_template
                dots = "." * (left_padding - len(name))
                pids = []
                try:
                    with psproc.oneshot():
                        stats = {
                            "name": name,
                            "dots": dots,
                            "cpu": psproc.cpu_percent(),
                            "mem": psproc.memory_percent(self.sys_stats_mem_type),
                            "m_type": self.sys_stats_mem_type.upper(),
                        }
                        if self.sys_stats_no_children is False:
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
                                        remove_from_stats.add(name)
                                        continue
                                    try:
                                        c_mem += child.memory_percent(self.sys_stats_mem_type)
                                        stats["c_count"] += 1
                                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                                        continue
                                if stats["c_count"]:
                                    stats["c_mem"] = "{:6.2f}".format(c_mem)
                                else:
                                    template = no_children_template
                        self.terminalreporter.write(template.format(**stats))
                except psutil.NoSuchProcess:
                    remove_from_stats.add(name)
                    continue
            if remove_from_stats:
                for name in remove_from_stats:
                    self.stats_processes.pop(name)


def pytest_addoption(parser):
    """
    register argparse-style options and ini-style config values.
    """
    output_options_group = parser.getgroup("Output Options")
    output_options_group.addoption(
        "--sys-stats",
        default=False,
        action="store_true",
        help="Print System CPU and MEM statistics after each test execution.",
    )
    output_options_group.addoption(
        "--sys-stats-no-children",
        default=False,
        action="store_true",
        help="Don't include child processes memory statistics.",
    )
    output_options_group.addoption(
        "--sys-stats-uss-mem",
        default=False,
        action="store_true",
        help='Use the USS("Unique Set Size", memory unique to a process which would be freed if the process was '
        "terminated) memory instead which is more expensive to calculate.",
    )


@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    if session.config.getoption("--sys-stats") is True:
        stats_processes = OrderedDict((("Test Suite Run", psutil.Process(os.getpid())),))
    else:
        stats_processes = None
    session.stats_processes = stats_processes

    terminalreporter = session.config.pluginmanager.getplugin("terminalreporter")
    sys_stats_reporter = SystemStatsReporter(
        config=session.config, stats_processes=stats_processes, terminalreporter=terminalreporter
    )
    session.config.pluginmanager.register(sys_stats_reporter, "saltfactories-sysstats-reporter")
