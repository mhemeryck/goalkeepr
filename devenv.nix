{ pkgs, lib, ... }:
let
  postgresEnv = {
    POSTGRES_DB = "goalkeepr";
    POSTGRES_HOST = "127.0.0.1";
    POSTGRES_PASSWORD = "goalkeepr";
    POSTGRES_USER = "goalkeepr";
  };
  postgresEnvCommand = lib.concatStringsSep " " (
    lib.mapAttrsToList (name: value: "${name}=${lib.escapeShellArg value}") postgresEnv
  );
in
{
  languages.python = {
    enable = true;
    package = pkgs.python314;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  packages = with pkgs; [
    nushell
    ruff
  ];

  services.postgres = {
    enable = true;
    package = pkgs.postgresql_18;
    listen_addresses = postgresEnv.POSTGRES_HOST;
    port = 5432;
    settings.shared_memory_type = "mmap";
    initialDatabases = [
      {
        name = postgresEnv.POSTGRES_DB;
        user = postgresEnv.POSTGRES_USER;
        pass = postgresEnv.POSTGRES_PASSWORD;
      }
    ];
  };

  scripts = {
    test.exec = "uv run pytest";
    lint.exec = "ruff check .";
    format.exec = "ruff format .";
    typecheck.exec = "uv run mypy .";
    manage.exec = ''
      ${postgresEnvCommand} uv run python manage.py "$@"
    '';
  };

  tasks = {
    "db:migrate" = {
      exec = "uv run python manage.py migrate";
      env = postgresEnv;
    };
  };

  processes.server = {
    exec = "uv run uvicorn goalkeepr.asgi:application --reload";
    env = postgresEnv;
    start.enable = false;
    after = [
      "devenv:processes:postgres"
      "db:migrate"
    ];
  };

}
