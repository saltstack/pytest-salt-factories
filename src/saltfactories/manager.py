"""
Salt Factories Manager.

..
    PYTEST_DONT_REWRITE
"""
import logging
import os
import pathlib
import sys

import attr

from saltfactories import CODE_ROOT_DIR
from saltfactories import daemons
from saltfactories.bases import SaltMixin
from saltfactories.utils import cast_to_pathlib_path
from saltfactories.utils import cli_scripts
from saltfactories.utils import running_username

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class FactoriesManager:
    """
    Factories manager implementation.

    The :class:`FactoriesManager` is responsible for configuring and spawning Salt Daemons and
    making sure that any salt CLI tools are "targeted" to the right daemon.

    It also keeps track of which daemons were started and adds their termination routines to PyTest's
    request finalization routines.

    If process statistics are enabled, it also adds the started daemons to those statistics.

    :keyword pathlib.Path, str root_dir:
    :keyword int log_server_port:
        The port the log server should listen at
    :keyword int log_server_level:
        The level of the log server
    :keyword str log_server_host:
        The hostname/ip address of the host running the logs server. Defaults to "localhost".
    :keyword str code_dir:
        The path to the code root directory of the project being tested. This is important for proper
        code-coverage paths.
    :keyword bool inject_coverage:
        Inject code-coverage related code in the generated CLI scripts
    :keyword bool inject_sitecustomize:
        Inject code in the generated CLI scripts in order for our `sitecustomise.py` to be loaded by
        subprocesses.
    :keyword str cwd:
        The path to the current working directory
    :keyword dict environ:
        A dictionary of `key`, `value` pairs to add to the environment.
    :keyword bool slow_stop:
        Whether to terminate the processes by sending a :py:attr:`SIGTERM` signal or by calling
        :py:meth:`~subprocess.Popen.terminate` on the sub-process.
        When code coverage is enabled, one will want `slow_stop` set to `True` so that coverage data
        can be written down to disk.
    :keyword int start_timeout:
        The amount of time, in seconds, to wait, until a subprocess is considered as not started.
    :type stats_processes: pytestsysstats.plugin.StatsProcesses
    :keyword stats_processes:
        This will be an `StatsProcesses` class instantiated on the :py:func:`~_pytest.hookspec.pytest_sessionstart`
        hook accessible as a session scoped `stats_processes` fixture.
    :keyword bool system_install:
        If true, the daemons and CLI's are run against a system installed salt setup, ie, the default
        salt system paths apply.
    """

    root_dir = attr.ib(converter=cast_to_pathlib_path)
    tmp_root_dir = attr.ib(init=False)
    log_server_port = attr.ib()
    log_server_level = attr.ib()
    log_server_host = attr.ib()
    code_dir = attr.ib(default=None)
    inject_coverage = attr.ib(default=False)
    inject_sitecustomize = attr.ib(default=False)
    cwd = attr.ib(factory=pathlib.Path.cwd)
    environ = attr.ib(factory=os.environ.copy)
    slow_stop = attr.ib(default=True)
    start_timeout = attr.ib(default=None)
    stats_processes = attr.ib(repr=False, default=None)
    system_install = attr.ib(repr=False, default=False)
    event_listener = attr.ib(repr=False)

    # Internal attributes
    scripts_dir = attr.ib(default=None, init=False, repr=False)

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        self.tmp_root_dir = pathlib.Path(self.root_dir)
        self.tmp_root_dir.mkdir(exist_ok=True)
        if self.system_install is False:
            self.root_dir = self.tmp_root_dir
        else:
            self.root_dir = pathlib.Path("/")
        if self.start_timeout is None:
            if not sys.platform.startswith(("win", "darwin")):
                self.start_timeout = 60
            else:
                # Windows and macOS are just slower
                self.start_timeout = 120

        if self.system_install is False:
            # Setup the internal attributes
            self.scripts_dir = self.root_dir / "scripts"
            self.scripts_dir.mkdir(exist_ok=True)

    @staticmethod
    def get_salt_log_handlers_path():
        """
        Returns the path to the Salt log handler this plugin provides.
        """
        return CODE_ROOT_DIR / "utils" / "saltext" / "log_handlers"

    @staticmethod
    def get_salt_engines_path():
        """
        Returns the path to the Salt engine this plugin provides.
        """
        return CODE_ROOT_DIR / "utils" / "saltext" / "engines"

    def final_minion_config_tweaks(self, config):
        """
        Final tweaks to the minion configuration.
        """
        pytest_key = "pytest-minion"
        if pytest_key not in config:  # pragma: no cover
            config[pytest_key] = {}
        config[pytest_key]["returner_address"] = self.event_listener.address
        self.final_common_config_tweaks(config, "minion")

    def final_master_config_tweaks(self, config):
        """
        Final tweaks to the master configuration.
        """
        pytest_key = "pytest-master"
        if pytest_key not in config:  # pragma: no cover
            config[pytest_key] = {}
        config[pytest_key]["returner_address"] = self.event_listener.address
        self.final_common_config_tweaks(config, "master")

    def final_syndic_config_tweaks(self, config):
        """
        Final tweaks to the syndic configuration.
        """
        self.final_common_config_tweaks(config, "syndic")

    def final_proxy_minion_config_tweaks(self, config):
        """
        Final tweaks to the proxy-minion configuration.
        """
        self.final_common_config_tweaks(config, "minion")

    def final_cloud_config_tweaks(self, config):
        """
        Final tweaks to the cloud configuration.
        """
        self.final_common_config_tweaks(config, "cloud")

    def final_common_config_tweaks(self, config, role):
        """
        Final common tweaks to the configuration.
        """
        config.setdefault("engines", [])
        if "pytest" not in config["engines"]:
            config["engines"].append("pytest")

        config.setdefault("user", running_username())
        if not config["user"]:  # pragma: no cover
            # If this value is empty, None, False, just remove it
            config.pop("user")

        pytest_key = "pytest-{}".format(role)
        if pytest_key not in config:
            config[pytest_key] = {}

        pytest_config = config[pytest_key]
        if "log" not in pytest_config:  # pragma: no cover
            pytest_config["log"] = {}

        log_config = pytest_config["log"]
        log_config.setdefault("host", self.log_server_host)
        log_config.setdefault("port", self.log_server_port)
        log_config.setdefault("level", "debug")

    def salt_master_daemon(
        self,
        master_id,
        order_masters=False,
        master_of_masters=None,
        defaults=None,
        overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.master.SaltMaster,
        **factory_class_kwargs
    ):
        """
        Return a salt-master instance.

        Args:
            master_id(str):
                The master ID
            order_masters(bool):
                Boolean flag to set if this master is going to control other masters(ie, master of masters), like,
                for example, in a :ref:`Syndic <salt:syndic>` topology scenario
            master_of_masters(:py:class:`saltfactories.daemons.master.SaltMaster`):
                A :py:class:`saltfactories.daemons.master.SaltMaster` instance, like, for example,
                in a :ref:`Syndic <salt:syndic>` topology scenario
            defaults(dict):
                A dictionary of default configuration to use when configuring the master
            overrides(dict):
                A dictionary of configuration overrides to use when configuring the master
            max_start_attempts(int):
                How many attempts should be made to start the master in case of failure to validate that its running
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`saltfactories.daemons.master.SaltMaster`

        Returns:
            :py:class:`saltfactories.daemons.master.SaltMaster`:
                The master process class instance
        """
        root_dir = self.get_root_dir_for_daemon(
            master_id, defaults=defaults, factory_class=factory_class
        )
        config = factory_class.configure(
            self,
            master_id,
            root_dir=root_dir,
            defaults=defaults,
            overrides=overrides,
            order_masters=order_masters,
            master_of_masters=master_of_masters,
        )
        self.final_master_config_tweaks(config)
        loaded_config = factory_class.write_config(config)
        if self.stats_processes is not None:
            factory_class_kwargs.setdefault("stats_processes", self.stats_processes)
        return self._get_factory_class_instance(
            "salt-master",
            loaded_config,
            factory_class,
            master_id,
            max_start_attempts,
            start_timeout,
            **factory_class_kwargs
        )

    def salt_minion_daemon(
        self,
        minion_id,
        master=None,
        defaults=None,
        overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.minion.SaltMinion,
        **factory_class_kwargs
    ):
        """
        Return a salt-minion instance.

        Args:
            minion_id(str):
                The minion ID
            master(:py:class:`saltfactories.daemons.master.SaltMaster`):
                An instance of :py:class:`saltfactories.daemons.master.SaltMaster` that
                this minion will connect to.
            defaults(dict):
                A dictionary of default configuration to use when configuring the minion
            overrides(dict):
                A dictionary of configuration overrides to use when configuring the minion
            max_start_attempts(int):
                How many attempts should be made to start the minion in case of failure to validate that its running
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.daemons.minion.SaltMinion`

        Returns:
            :py:class:`~saltfactories.daemons.minion.SaltMinion`:
                The minion process class instance
        """
        root_dir = self.get_root_dir_for_daemon(
            minion_id, defaults=defaults, factory_class=factory_class
        )

        config = factory_class.configure(
            self,
            minion_id,
            root_dir=root_dir,
            defaults=defaults,
            overrides=overrides,
            master=master,
        )
        self.final_minion_config_tweaks(config)
        loaded_config = factory_class.write_config(config)
        if self.stats_processes is not None:
            factory_class_kwargs.setdefault("stats_processes", self.stats_processes)
        return self._get_factory_class_instance(
            "salt-minion",
            loaded_config,
            factory_class,
            minion_id,
            max_start_attempts,
            start_timeout,
            **factory_class_kwargs
        )

    def salt_syndic_daemon(
        self,
        syndic_id,
        master_of_masters=None,
        defaults=None,
        overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.syndic.SaltSyndic,
        master_defaults=None,
        master_overrides=None,
        master_factory_class=daemons.master.SaltMaster,
        minion_defaults=None,
        minion_overrides=None,
        minion_factory_class=daemons.minion.SaltMinion,
        **factory_class_kwargs
    ):
        """
        Return a salt-syndic instance.

        Args:
            syndic_id(str):
                The Syndic ID. This ID will be shared by the ``salt-master``, ``salt-minion`` and ``salt-syndic``
                processes.
            master_of_masters(:py:class:`saltfactories.daemons.master.SaltMaster`):
                An instance of :py:class:`saltfactories.daemons.master.SaltMaster` that the
                master configured in this :ref:`Syndic <salt:syndic>` topology scenario shall connect to.
            defaults(dict):
                A dictionary of default configurations with three top level keys, ``master``, ``minion`` and
                ``syndic``, to use when configuring the  ``salt-master``, ``salt-minion`` and ``salt-syndic``
                respectively.
            overrides(dict):
                A dictionary of configuration overrides with three top level keys, ``master``, ``minion`` and
                ``syndic``, to use when configuring the  ``salt-master``, ``salt-minion`` and ``salt-syndic``
                respectively.
            max_start_attempts(int):
                How many attempts should be made to start the syndic in case of failure to validate that its running
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.daemons.syndic.SaltSyndic`

        Returns:
            :py:class:`~saltfactories.daemons.syndic.SaltSyndic`:
                The syndic process class instance
        """
        root_dir = self.get_root_dir_for_daemon(
            syndic_id, defaults=defaults, factory_class=factory_class
        )

        master_config = master_factory_class.configure(
            self,
            syndic_id,
            root_dir=root_dir,
            defaults=master_defaults,
            overrides=master_overrides,
            master_of_masters=master_of_masters,
        )
        # Remove syndic related options
        for key in list(master_config):
            if key.startswith("syndic_"):
                master_config.pop(key)
        self.final_master_config_tweaks(master_config)
        master_loaded_config = master_factory_class.write_config(master_config)
        if self.stats_processes is not None:
            factory_class_kwargs.setdefault("stats_processes", self.stats_processes)
        master_factory = self._get_factory_class_instance(
            "salt-master",
            master_loaded_config,
            master_factory_class,
            syndic_id,
            max_start_attempts,
            start_timeout,
        )

        minion_config = minion_factory_class.configure(
            self,
            syndic_id,
            root_dir=root_dir,
            defaults=minion_defaults,
            overrides=minion_overrides,
            master=master_factory,
        )
        self.final_minion_config_tweaks(minion_config)
        minion_loaded_config = minion_factory_class.write_config(minion_config)
        minion_factory = self._get_factory_class_instance(
            "salt-minion",
            minion_loaded_config,
            minion_factory_class,
            syndic_id,
            max_start_attempts,
            start_timeout,
        )

        syndic_config = factory_class.default_config(
            root_dir,
            syndic_id=syndic_id,
            defaults=defaults,
            overrides=overrides,
            master_of_masters=master_of_masters,
            system_install=self.system_install,
        )
        self.final_syndic_config_tweaks(syndic_config)
        syndic_loaded_config = factory_class.write_config(syndic_config)
        factory = self._get_factory_class_instance(
            "salt-syndic",
            syndic_loaded_config,
            factory_class,
            syndic_id,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout,
            master=master_factory,
            minion=minion_factory,
            **factory_class_kwargs
        )

        # We need the syndic master and minion running
        factory.before_start(master_factory.start)
        factory.before_start(minion_factory.start)
        return factory

    def salt_proxy_minion_daemon(
        self,
        proxy_minion_id,
        master=None,
        defaults=None,
        overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.proxy.SaltProxyMinion,
        **factory_class_kwargs
    ):
        """
        Return a salt proxy-minion instance.

        Args:
            proxy_minion_id(str):
                The proxy minion ID
            master(:py:class:`saltfactories.daemons.master.SaltMaster`):
                An instance of :py:class:`saltfactories.daemons.master.SaltMaster` that this minion
                will connect to.
            defaults(dict):
                A dictionary of default configuration to use when configuring the proxy minion
            overrides(dict):
                A dictionary of configuration overrides to use when configuring the proxy minion
            max_start_attempts(int):
                How many attempts should be made to start the proxy minion in case of failure to validate that
                its running
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.daemons.proxy.SaltProxyMinion`

        Returns:
            :py:class:`~saltfactories.daemons.proxy.SaltProxyMinion`:
                The proxy minion process class instance
        """
        root_dir = self.get_root_dir_for_daemon(
            proxy_minion_id, defaults=defaults, factory_class=factory_class
        )

        config = factory_class.configure(
            self,
            proxy_minion_id,
            root_dir=root_dir,
            defaults=defaults,
            overrides=overrides,
            master=master,
        )
        self.final_proxy_minion_config_tweaks(config)
        loaded_config = factory_class.write_config(config)
        if self.stats_processes is not None:
            factory_class_kwargs.setdefault("stats_processes", self.stats_processes)
        return self._get_factory_class_instance(
            "salt-proxy",
            loaded_config,
            factory_class,
            proxy_minion_id,
            max_start_attempts,
            start_timeout,
            **factory_class_kwargs
        )

    def salt_api_daemon(
        self,
        master,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.api.SaltApi,
        **factory_class_kwargs
    ):
        """
        Return a salt-api instance.

        Please see py:class:`~saltfactories.manager.FactoriesManager.salt_master_daemon` for argument
        documentation.

        Returns:
            :py:class:`~saltfactories.daemons.api.SaltApi`:
                The salt-api process class instance
        """
        return self._get_factory_class_instance(
            "salt-api",
            master.config,
            factory_class,
            master.id,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout,
            **factory_class_kwargs
        )

    def get_sshd_daemon(
        self,
        config_dir=None,
        listen_address=None,
        listen_port=None,
        sshd_config_dict=None,
        display_name=None,
        script_name="sshd",
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.sshd.Sshd,
        **factory_class_kwargs
    ):
        """
        Return an SSHD daemon instance.

        Args:
            max_start_attempts(int):
                How many attempts should be made to start the proxy minion in case of failure to validate that
                its running
            config_dir(pathlib.Path):
                The path to the sshd config directory
            listen_address(str):
                The address where the sshd server will listen to connections. Defaults to 127.0.0.1
            listen_port(int):
                The port where the sshd server will listen to connections
            sshd_config_dict(dict):
                A dictionary of key-value pairs to construct the sshd config file
            script_name(str):
                The name or path to the binary to run. Defaults to ``sshd``.
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.daemons.sshd.Sshd`

        Returns:
            :py:class:`~saltfactories.daemons.sshd.Sshd`:
                The sshd process class instance
        """
        if config_dir is None:
            config_dir = self.get_root_dir_for_daemon("sshd", factory_class=factory_class)
        try:
            config_dir = pathlib.Path(config_dir.strpath).resolve()
        except AttributeError:
            config_dir = pathlib.Path(config_dir).resolve()
        if self.stats_processes is not None:
            factory_class_kwargs.setdefault("stats_processes", self.stats_processes)
        return factory_class(
            start_timeout=start_timeout or self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_start_attempts=max_start_attempts,
            script_name=script_name,
            display_name=display_name or "SSHD",
            config_dir=config_dir,
            listen_address=listen_address,
            listen_port=listen_port,
            sshd_config_dict=sshd_config_dict,
            **factory_class_kwargs
        )

    def get_container(
        self,
        container_name,
        image_name,
        display_name=None,
        factory_class=daemons.container.Container,
        max_start_attempts=3,
        start_timeout=None,
        **factory_class_kwargs
    ):
        """
        Return a container instance.

        Args:
            container_name(str):
                The name to give the container
            image_name(str):
                The image to use
            display_name(str):
                Human readable name for the factory
            factory_class:
                A factory class. (Default :py:class:`~saltfactories.daemons.container.Container`)
            max_start_attempts(int):
                How many attempts should be made to start the container in case of failure to validate that
                its running.
            start_timeout(int):
                The amount of time, in seconds, to wait, until the container is considered as not started.
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.daemons.container.Container`

        Returns:
            :py:class:`~saltfactories.daemons.container.Container`:
                The factory instance
        """
        return factory_class(
            name=container_name,
            image=image_name,
            display_name=display_name or container_name,
            environ=self.environ,
            cwd=self.cwd,
            start_timeout=start_timeout or self.start_timeout,
            max_start_attempts=max_start_attempts,
            **factory_class_kwargs
        )

    def get_salt_script_path(self, script_name):
        """
        Return the path to the customized script path, generating one if needed.
        """
        if self.system_install is True:
            return script_name
        return cli_scripts.generate_script(
            self.scripts_dir,
            script_name,
            code_dir=self.code_dir,
            inject_coverage=self.inject_coverage,
            inject_sitecustomize=self.inject_sitecustomize,
        )

    def _get_factory_class_instance(
        self,
        script_name,
        daemon_config,
        factory_class,
        daemon_id,
        max_start_attempts,
        start_timeout,
        **factory_class_kwargs
    ):
        """
        Helper method to instantiate daemon factories.
        """
        if self.system_install:
            script_path = script_name
        else:
            script_path = self.get_salt_script_path(script_name)
        factory = factory_class(
            config=daemon_config,
            start_timeout=start_timeout or self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_start_attempts=max_start_attempts,
            event_listener=self.event_listener,
            factories_manager=self,
            script_name=script_path,
            system_install=self.system_install,
            **factory_class_kwargs
        )
        return factory

    def get_root_dir_for_daemon(self, daemon_id, defaults=None, factory_class=None):
        """
        Return a root directory for the passed daemon.
        """
        if defaults and "root_dir" in defaults:
            try:
                root_dir = pathlib.Path(defaults["root_dir"].strpath).resolve()
            except AttributeError:
                root_dir = pathlib.Path(defaults["root_dir"]).resolve()
            root_dir.mkdir(parents=True, exist_ok=True)
            return root_dir
        if self.system_install is True and issubclass(factory_class, SaltMixin):
            return self.root_dir
        elif self.system_install is True:
            root_dir = self.tmp_root_dir
        else:
            root_dir = self.root_dir
        counter = 1
        root_dir = root_dir / daemon_id
        while True:
            if not root_dir.is_dir():
                break
            root_dir = self.root_dir / "{}_{}".format(daemon_id, counter)
            counter += 1
        root_dir.mkdir(parents=True, exist_ok=True)
        return root_dir
