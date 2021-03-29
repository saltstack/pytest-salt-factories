"""
..
    PYTEST_DONT_REWRITE


saltfactories.factories.manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt Factories Manager
"""
import logging
import pathlib
import sys

import attr

import saltfactories
from saltfactories.factories import daemons
from saltfactories.factories.base import SaltFactory
from saltfactories.utils import cli_scripts
from saltfactories.utils import running_username

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class FactoriesManager:
    """
    The :class:`FactoriesManager` is responsible for configuring and spawning Salt Daemons and
    making sure that any salt CLI tools are "targeted" to the right daemon.

    It also keeps track of which daemons were started and adds their termination routines to PyTest's
    request finalization routines.

    If process statistics are enabled, it also adds the started daemons to those statistics.

    Args:
        root_dir:
        log_server_port(int):
            The port the log server should listen at
        log_server_level(int):
            The level of the log server
        log_server_host(str):
            The hostname/ip address of the host running the logs server. Defaults to "localhost".
        code_dir(str):
            The path to the code root directory of the project being tested. This is important for proper
            code-coverage paths.
        inject_coverage(bool):
            Inject code-coverage related code in the generated CLI scripts
        inject_sitecustomize(bool):
            Inject code in the generated CLI scripts in order for our `sitecustomise.py` to be loaded by
            subprocesses.
        cwd(str):
            The path to the current working directory
        environ(dict):
            A dictionary of `key`, `value` pairs to add to the environment.
        slow_stop(bool):
            Whether to terminate the processes by sending a :py:attr:`SIGTERM` signal or by calling
            :py:meth:`~subprocess.Popen.terminate` on the sub-process.
            When code coverage is enabled, one will want `slow_stop` set to `True` so that coverage data
            can be written down to disk.
        start_timeout(int):
            The amount of time, in seconds, to wait, until a subprocess is considered as not started.
        stats_processes(:py:class:`saltfactories.plugins.sysstats.StatsProcesses`):
            This will be an `StatsProcesses` class instantiated on the :py:func:`~_pytest.hookspec.pytest_sessionstart`
            hook accessible as a session scoped `stats_processes` fixture.
        system_install(bool):
            If true, the daemons and CLI's are run against a system installed salt setup, ie, the default
            salt system paths apply.
    """

    root_dir = attr.ib()
    tmp_root_dir = attr.ib(init=False)
    log_server_port = attr.ib()
    log_server_level = attr.ib()
    log_server_host = attr.ib()
    code_dir = attr.ib(default=None)
    inject_coverage = attr.ib(default=False)
    inject_sitecustomize = attr.ib(default=False)
    cwd = attr.ib(default=None)
    environ = attr.ib(default=None)
    slow_stop = attr.ib(default=True)
    start_timeout = attr.ib(default=None)
    stats_processes = attr.ib(repr=False, default=None)
    system_install = attr.ib(repr=False, default=False)
    event_listener = attr.ib(repr=False)

    # Internal attributes
    scripts_dir = attr.ib(default=None, init=False, repr=False)

    def __attrs_post_init__(self):
        self.tmp_root_dir = pathlib.Path(self.root_dir.strpath)
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
        Returns the path to the Salt log handler this plugin provides
        """
        return saltfactories.CODE_ROOT_DIR / "utils" / "salt" / "log_handlers"

    @staticmethod
    def get_salt_engines_path():
        """
        Returns the path to the Salt engine this plugin provides
        """
        return saltfactories.CODE_ROOT_DIR / "utils" / "salt" / "engines"

    def final_minion_config_tweaks(self, config):
        pytest_key = "pytest-minion"
        if pytest_key not in config:
            config[pytest_key] = {}
        config[pytest_key]["returner_address"] = self.event_listener.address
        self.final_common_config_tweaks(config, "minion")

    def final_master_config_tweaks(self, config):
        pytest_key = "pytest-master"
        if pytest_key not in config:
            config[pytest_key] = {}
        config[pytest_key]["returner_address"] = self.event_listener.address
        self.final_common_config_tweaks(config, "master")

    def final_syndic_config_tweaks(self, config):
        self.final_common_config_tweaks(config, "syndic")

    def final_proxy_minion_config_tweaks(self, config):
        self.final_common_config_tweaks(config, "minion")

    def final_cloud_config_tweaks(self, config):
        self.final_common_config_tweaks(config, "cloud")

    def final_common_config_tweaks(self, config, role):
        config.setdefault("engines", [])
        if "pytest" not in config["engines"]:
            config["engines"].append("pytest")

        if "engines_dirs" not in config:
            config["engines_dirs"] = []
        config["engines_dirs"].insert(0, str(FactoriesManager.get_salt_engines_path()))
        config.setdefault("user", running_username())
        if not config["user"]:
            # If this value is empty, None, False, just remove it
            config.pop("user")
        if "log_forwarding_consumer" not in config:
            # Still using old logging, let's add our custom log handler
            if "log_handlers_dirs" not in config:
                config["log_handlers_dirs"] = []
            config["log_handlers_dirs"].insert(
                0, str(FactoriesManager.get_salt_log_handlers_path())
            )

        pytest_key = "pytest-{}".format(role)
        if pytest_key not in config:
            config[pytest_key] = {}

        pytest_config = config[pytest_key]
        if "log" not in pytest_config:
            pytest_config["log"] = {}

        log_config = pytest_config["log"]
        log_config.setdefault("host", self.log_server_host)
        log_config.setdefault("port", self.log_server_port)
        log_config.setdefault("level", self.log_server_level)

    def get_salt_master_daemon(
        self,
        master_id,
        order_masters=False,
        master_of_masters=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.master.SaltMasterFactory,
        **factory_class_kwargs
    ):
        """
        Configure a salt-master

        Args:
            master_id(str):
                The master ID
            order_masters(bool):
                Boolean flag to set if this master is going to control other masters(ie, master of masters), like,
                for example, in a :ref:`Syndic <salt:syndic>` topology scenario
            master_of_masters(:py:class:`saltfactories.factories.daemons.master.SaltMasterFactory`):
                A :py:class:`saltfactories.factories.daemons.master.SaltMasterFactory` instance, like, for example,
                in a :ref:`Syndic <salt:syndic>` topology scenario
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the master
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the master
            max_start_attempts(int):
                How many attempts should be made to start the master in case of failure to validate that its running
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`saltfactories.factories.daemons.master.SaltMasterFactory`

        Returns:
            :py:class:`saltfactories.factories.daemons.master.SaltMasterFactory`:
                The master process class instance
        """
        root_dir = self.get_root_dir_for_daemon(
            master_id, config_defaults=config_defaults, factory_class=factory_class
        )
        config = factory_class.configure(
            self,
            master_id,
            root_dir=root_dir,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            order_masters=order_masters,
            master_of_masters=master_of_masters,
        )
        self.final_master_config_tweaks(config)
        loaded_config = factory_class.write_config(config)
        return self._get_factory_class_instance(
            "salt-master",
            loaded_config,
            factory_class,
            master_id,
            max_start_attempts,
            start_timeout,
            **factory_class_kwargs
        )

    def get_salt_minion_daemon(
        self,
        minion_id,
        master=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.minion.SaltMinionFactory,
        **factory_class_kwargs
    ):
        """
        Spawn a salt-minion

        Args:
            minion_id(str):
                The minion ID
            master(:py:class:`saltfactories.factories.daemons.master.SaltMasterFactory`):
                An instance of :py:class:`saltfactories.factories.daemons.master.SaltMasterFactory` that
                this minion will connect to.
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the minion
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the minion
            max_start_attempts(int):
                How many attempts should be made to start the minion in case of failure to validate that its running
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.minion.SaltMinionFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.minion.SaltMinionFactory`:
                The minion process class instance
        """
        root_dir = self.get_root_dir_for_daemon(
            minion_id, config_defaults=config_defaults, factory_class=factory_class
        )

        config = factory_class.configure(
            self,
            minion_id,
            root_dir=root_dir,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            master=master,
        )
        self.final_minion_config_tweaks(config)
        loaded_config = factory_class.write_config(config)
        return self._get_factory_class_instance(
            "salt-minion",
            loaded_config,
            factory_class,
            minion_id,
            max_start_attempts,
            start_timeout,
            **factory_class_kwargs
        )

    def get_salt_syndic_daemon(
        self,
        syndic_id,
        master_of_masters=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.syndic.SaltSyndicFactory,
        master_config_defaults=None,
        master_config_overrides=None,
        master_factory_class=daemons.master.SaltMasterFactory,
        minion_config_defaults=None,
        minion_config_overrides=None,
        minion_factory_class=daemons.minion.SaltMinionFactory,
        **factory_class_kwargs
    ):
        """
        Spawn a salt-syndic

        Args:
            syndic_id(str):
                The Syndic ID. This ID will be shared by the ``salt-master``, ``salt-minion`` and ``salt-syndic``
                processes.
            master_of_masters(:py:class:`saltfactories.factories.daemons.master.SaltMasterFactory`):
                An instance of :py:class:`saltfactories.factories.daemons.master.SaltMasterFactory` that the
                master configured in this :ref:`Syndic <salt:syndic>` topology scenario shall connect to.
            config_defaults(dict):
                A dictionary of default configurations with three top level keys, ``master``, ``minion`` and
                ``syndic``, to use when configuring the  ``salt-master``, ``salt-minion`` and ``salt-syndic``
                respectively.
            config_overrides(dict):
                A dictionary of configuration overrides with three top level keys, ``master``, ``minion`` and
                ``syndic``, to use when configuring the  ``salt-master``, ``salt-minion`` and ``salt-syndic``
                respectively.
            max_start_attempts(int):
                How many attempts should be made to start the syndic in case of failure to validate that its running
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.syndic.SaltSyndicFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.syndic.SaltSyndicFactory`:
                The syndic process class instance
        """

        root_dir = self.get_root_dir_for_daemon(
            syndic_id, config_defaults=config_defaults, factory_class=factory_class
        )

        master_config = master_factory_class.configure(
            self,
            syndic_id,
            root_dir=root_dir,
            config_defaults=master_config_defaults,
            config_overrides=master_config_overrides,
            master_of_masters=master_of_masters,
        )
        # Remove syndic related options
        for key in list(master_config):
            if key.startswith("syndic_"):
                master_config.pop(key)
        self.final_master_config_tweaks(master_config)
        master_loaded_config = master_factory_class.write_config(master_config)
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
            config_defaults=minion_config_defaults,
            config_overrides=minion_config_overrides,
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
            config_defaults=config_defaults,
            config_overrides=config_overrides,
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
        factory.register_before_start_callback(master_factory.start)
        factory.register_before_start_callback(minion_factory.start)
        return factory

    def get_salt_proxy_minion_daemon(
        self,
        proxy_minion_id,
        master=None,
        config_defaults=None,
        config_overrides=None,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.proxy.SaltProxyMinionFactory,
        **factory_class_kwargs
    ):
        """
        Spawn a salt-proxy

        Args:
            proxy_minion_id(str):
                The proxy minion ID
            master(:py:class:`saltfactories.factories.daemons.master.SaltMasterFactory`):
                An instance of :py:class:`saltfactories.factories.daemons.master.SaltMasterFactory` that this minion
                will connect to.
            config_defaults(dict):
                A dictionary of default configuration to use when configuring the proxy minion
            config_overrides(dict):
                A dictionary of configuration overrides to use when configuring the proxy minion
            max_start_attempts(int):
                How many attempts should be made to start the proxy minion in case of failure to validate that
                its running
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.proxy.SaltProxyMinionFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.proxy.SaltProxyMinionFactory`:
                The proxy minion process class instance
        """
        root_dir = self.get_root_dir_for_daemon(
            proxy_minion_id, config_defaults=config_defaults, factory_class=factory_class
        )

        config = factory_class.configure(
            self,
            proxy_minion_id,
            root_dir=root_dir,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            master=master,
        )
        self.final_proxy_minion_config_tweaks(config)
        loaded_config = factory_class.write_config(config)
        return self._get_factory_class_instance(
            "salt-proxy",
            loaded_config,
            factory_class,
            proxy_minion_id,
            max_start_attempts,
            start_timeout,
            **factory_class_kwargs
        )

    def get_salt_api_daemon(
        self,
        master,
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.api.SaltApiFactory,
        **factory_class_kwargs
    ):
        """
        Spawn a salt-api

        Please see py:class:`~saltfactories.factories.manager.FactoriesManager.get_salt_master_daemon` for argument
        documentation.

        Returns:
            :py:class:`~saltfactories.factories.daemons.api.SaltApiFactory`:
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
        cli_script_name="sshd",
        max_start_attempts=3,
        start_timeout=None,
        factory_class=daemons.sshd.SshdDaemonFactory,
        **factory_class_kwargs
    ):
        """
        Start an sshd daemon

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
            cli_script_name(str):
                The name or path to the binary to run. Defaults to ``sshd``.
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.sshd.SshdDaemonFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.sshd.SshdDaemonFactory`:
                The sshd process class instance
        """
        if config_dir is None:
            config_dir = self.get_root_dir_for_daemon("sshd", factory_class=factory_class)
        try:
            config_dir = pathlib.Path(config_dir.strpath).resolve()
        except AttributeError:
            config_dir = pathlib.Path(config_dir).resolve()

        return factory_class(
            start_timeout=start_timeout or self.start_timeout,
            slow_stop=self.slow_stop,
            environ=self.environ,
            cwd=self.cwd,
            max_start_attempts=max_start_attempts,
            factories_manager=self,
            cli_script_name=cli_script_name,
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
        docker_client=None,
        display_name=None,
        factory_class=daemons.container.ContainerFactory,
        max_start_attempts=3,
        start_timeout=None,
        **factory_class_kwargs
    ):
        """
        Start a docker container

        Args:
            container_name(str):
                The name to give the container
            image_name(str):
                The image to use
            docker_client:
                An instance of the docker client to use
            display_name(str):
                Human readable name for the factory
            factory_class:
                A factory class. (Default :py:class:`~saltfactories.factories.daemons.container.ContainerFactory`)
            max_start_attempts(int):
                How many attempts should be made to start the container in case of failure to validate that
                its running.
            start_timeout(int):
                The amount of time, in seconds, to wait, until the container is considered as not started.
            factory_class_kwargs(dict):
                Extra keyword arguments to pass to :py:class:`~saltfactories.factories.daemons.container.ContainerFactory`

        Returns:
            :py:class:`~saltfactories.factories.daemons.container.ContainerFactory`:
                The factory instance
        """
        return factory_class(
            name=container_name,
            image=image_name,
            docker_client=docker_client,
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
        Helper method to instantiate daemon factories
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
            cli_script_name=script_path,
            system_install=self.system_install,
            **factory_class_kwargs
        )
        return factory

    def get_root_dir_for_daemon(self, daemon_id, config_defaults=None, factory_class=None):
        if config_defaults and "root_dir" in config_defaults:
            try:
                root_dir = pathlib.Path(config_defaults["root_dir"].strpath).resolve()
            except AttributeError:
                root_dir = pathlib.Path(config_defaults["root_dir"]).resolve()
            root_dir.mkdir(parents=True, exist_ok=True)
            return root_dir
        if self.system_install is True and issubclass(factory_class, SaltFactory):
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
