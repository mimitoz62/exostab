"""Serve the exostab web app at <session URL>/exostab/. jupyter-server-proxy starts it on the first request."""

c = get_config()  # noqa: F821
c.ServerProxy.servers = {
    "exostab": {
        "command": [
            "python",
            "-m",
            "exostab.web",
            "--server.port={port}",
            "--server.headless=true",
            # The session is reached through a proxy, so the origin the browser sends differs from the app's host.
            "--server.enableCORS=false",
            "--server.enableXsrfProtection=false",
            # Nothing is edited in a Binder session, so the app need not watch its files.
            "--server.fileWatcherType=none",
            "--browser.gatherUsageStats=false",
            "--client.toolbarMode=viewer",
        ],
        "timeout": 120,
        "launcher_entry": {"title": "exostab web app"},
    }
}
