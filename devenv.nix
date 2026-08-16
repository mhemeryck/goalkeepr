{ pkgs, ... }:
{
  languages.python = {
    enable = true;
    package = pkgs.python314;
    uv.enable = true;
  };

  packages = [
    pkgs.nushell
    pkgs.ruff
  ];

  scripts = {
    test.exec = "nu -c 'uv run pytest'";
    lint.exec = "nu -c 'ruff check .'";
    format.exec = "nu -c 'ruff format .'";
    typecheck.exec = "nu -c 'uv run mypy .'";
    migrate.exec = "nu -c 'uv run python manage.py migrate'";
    server.exec = "nu -c 'uv run uvicorn goalkeepr.asgi:application --reload'";
  };

  enterShell = ''
    uv sync
  '';
}
