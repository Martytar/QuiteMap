# QuiteMap

Crownsourced map of quiet places to work and study filtered by noise level, availability of Wi-Fi and more.

Presentation: [link](https://docs.google.com/presentation/d/1CUJr1Kskp0RIIE8Vm7223YR9ZhkgHkWw/edit?slide=id.p1#slide=id.p1)
## Getting Started

### Using Nix (Recommended)

If you have Nix installed, simply enter the development shell:

```bash
nix-shell
```

Then run the application:

```bash
uvicorn main:app
python3 ./quite_map_register_bot.py
```

### Using pip

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
uvicorn main:app
python3 ./quite_map_register_bot.py
```

The `--reload` flag enables auto-reload on code changes, perfect for development.

The `--host` and `--port` flags are used to change server endpoint.

### Environment Variables

This project uses `.env` and `.env.local` files for configuration.

Example contents of `.env` file provided in `.env.example` file.
