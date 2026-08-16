{ pkgs, ... }:
{
  languages.python = {
    enable = true;
    package = pkgs.python314;
    uv = {
      enable = true;
      sync.enable = false;
    };
  };

  packages = with pkgs; [
    nushell
    ruff
  ];

  scripts = {
    test.exec = "uv run pytest";
    lint.exec = "ruff check .";
    format.exec = "ruff format .";
    typecheck.exec = "uv run mypy .";
    migrate.exec = "uv run python manage.py migrate";
    server.exec = "uv run uvicorn goalkeepr.asgi:application --reload";
  };

  enterShell = ''
    uv sync
  '';
}
