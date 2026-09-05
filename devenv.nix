{
  config,
  pkgs,
  lib,
  ...
}:
let
  isCI = builtins.getEnv "CI" == "true";
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

  packages = [ pkgs.ruff ];

  env = {
    TF_VAR_billing_alert_email = config.secretspec.secrets.BILLING_ALERT_EMAIL;
  } // lib.optionalAttrs (!isCI) {
    AWS_PROFILE = "mhemeryck";
  };

  services.postgres = {
    enable = !config.devenv.isTesting;
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
    tests.exec = "uv run pytest";
    lint.exec = "ruff check .";
    format.exec = "ruff format .";
    typecheck.exec = "uv run mypy .";
    manage.exec = ''
      ${postgresEnvCommand} uv run python manage.py "$@"
    '';
    deploy = {
      package = pkgs.nushell;
      binary = "nu";
      packages = [ pkgs.terraform ];
      exec = ''
        cd infra/envs/mhemeryck/goalkeepr
        terraform init
        terraform fmt -check
        terraform validate
        terraform plan -out=tfplan
        terraform apply -auto-approve tfplan
      '';
    };
  };

  enterTest = ''
    uv run python manage.py collectstatic --noinput
    tests
    lint
    typecheck
  '';

  tasks = {
    "db:migrate" = {
      exec = "uv run python manage.py migrate";
      env = postgresEnv;
    };
  };

  processes = lib.optionalAttrs (!config.devenv.isTesting) {
    server = {
      exec = "uv run uvicorn goalkeepr.asgi:application --reload";
      env = postgresEnv;
      after = [
        "devenv:processes:postgres"
        "db:migrate"
      ];
    };
  };
}
