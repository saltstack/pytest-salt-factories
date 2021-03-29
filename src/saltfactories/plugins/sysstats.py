"""
    saltfactories.plugins.sysstats
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Process stats PyTest plugin interface
"""
import os
import sys
from collections import OrderedDict

import attr
import psutil
import pytest


@attr.s(kw_only=True, slots=True, hash=True)
class StatsProcesses:
    processes = attr.ib(init=False, default=attr.Factory(OrderedDict), hash=False)

    def add(self, display_name, process):
        if isinstance(process, int):
            # This is a process pid
            process = psutil.Process(process)
        self.processes[display_name] = process

    def remove(self, display_name):
        self.processes.pop(display_name, None)

    def items(self):
        return self.processes.items()

    def __iter__(self):
        return iter(self.processes)


@attr.s(kw_only=True, slots=True, hash=True)
class SystemStatsReporter:

    config = attr.ib(repr=False, hash=False)
    stats_processes = attr.ib(repr=False, hash=False)
    terminalreporter = attr.ib(repr=False, hash=False)
    show_sys_stats = attr.ib(init=False)
    sys_stats_no_children = attr.ib(init=False)
    sys_stats_mem_type = attr.ib(init=False)

    def __attrs_post_init__(self):
        self.show_sys_stats = (
            self.config.getoption("--sys-stats") is True
            and self.config.getoption("--no-sys-stats") is False
        )
        self.sys_stats_no_children = self.config.getoption("--sys-stats-no-children") is True
        if self.config.getoption("--sys-stats-uss-mem") is True:
            self.sys_stats_mem_type = "uss"
            if sys.platform.startswith("freebsd"):
                # FreeBSD doesn't apparently support uss
                self.sys_stats_mem_type = "rss"
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
                    self.stats_processes.remove(name)


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
        "--no-sys-stats",
        default=False,
        action="store_true",
        help="Do not print System CPU and MEM statistics after each test execution.",
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
    if (
        session.config.getoption("--sys-stats") is True
        and session.config.getoption("--no-sys-stats") is False
    ):
        stats_processes = StatsProcesses()
        stats_processes.add("Test Suite Run", os.getpid())
    else:
        stats_processes = None

    session.config.pluginmanager.register(stats_processes, "saltfactories-sysstats-processes")

    terminalreporter = session.config.pluginmanager.getplugin("terminalreporter")
    sys_stats_reporter = SystemStatsReporter(
        config=session.config, stats_processes=stats_processes, terminalreporter=terminalreporter
    )
    session.config.pluginmanager.register(sys_stats_reporter, "saltfactories-sysstats-reporter")


@pytest.fixture(scope="session")
def stats_processes(request):
    return request.config.pluginmanager.get_plugin("saltfactories-sysstats-processes")
