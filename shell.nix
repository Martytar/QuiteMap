{pkgs ? import <nixpkgs> {}}:
pkgs.mkShell {
  name = "fastapi-env";

  # Define your Python environment
  buildInputs = with pkgs; [
    (python312.withPackages (ps:
      with ps; [
        fastapi
        uvicorn
        jinja2
        sqlalchemy # ORM for database operations
        alembic # Database migrations
        python-dotenv # Environment variable management
        httpx # For testing HTTP endpoints
        pytest # For testing
        black # Code formatter
        isort # Import sorter
        mypy # Type checker
        passlib # Passwords
        python-jose # JWT
        python-multipart
        bcrypt
      ]))
  ];

  # Optional: environment variables
  shellHook = ''
    echo "🐍 FastAPI development environment loaded!"
    echo "Run your app with: uvicorn main:app --reload"
    echo "Database migrations: alembic upgrade head"
  '';
}
