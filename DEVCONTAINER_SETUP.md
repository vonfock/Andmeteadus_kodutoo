# Dev Container Setup

Everyone on the team uses the same Linux-based Docker environment. No manual Python installation needed.

## Prerequisites (install once)

1. **Docker Desktop** — [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
   - Windows: install and make sure it's running (whale icon in taskbar)
   - Mac: install and start Docker Desktop

2. **VSCode** — [code.visualstudio.com](https://code.visualstudio.com/)

3. **Dev Containers extension** — install inside VSCode:
   - Press `Ctrl+Shift+X`, search `Dev Containers`, install it
   - Extension ID: `ms-vscode-remote.remote-containers`

## Opening the project in the container

1. Clone the repo:
   ```bash
   git clone https://github.com/TereKruut/sissejuhatus_andmeteadusesse_grupitoo.git
   cd sissejuhatus_andmeteadusesse_grupitoo
   ```

2. Open in VSCode:
   ```bash
   code .
   ```

3. VSCode will detect the `.devcontainer` folder and show a popup:
   > **"Folder contains a Dev Container configuration file. Reopen in Container?"**
   
   Click **"Reopen in Container"**.
   
   If you miss the popup: press `Ctrl+Shift+P` → type `Dev Containers: Reopen in Container`

4. First time takes 3–5 minutes while Docker builds the image. After that it's instant.

5. You're now inside Ubuntu 24.04 with Python 3.12, DuckDB, pandas, scikit-learn, Streamlit and everything else pre-installed.

## Running things inside the container

Open the VSCode integrated terminal (`` Ctrl+` ``) — it's now running inside Linux:

```bash
# Run the data pipeline
python src/data_loader.py
python src/data_cleaner.py
python src/feature_engineering.py

# Launch Streamlit dashboard
streamlit run dashboard/app.py
# → opens at http://localhost:8501

# Launch JupyterLab
jupyter lab --ip=0.0.0.0 --no-browser
# → opens at http://localhost:8888
```

## Rebuilding the container

If `requirements.txt` or the `Dockerfile` changes, rebuild:

`Ctrl+Shift+P` → `Dev Containers: Rebuild Container`

## Troubleshooting

**"Docker not found" or container won't start**
→ Make sure Docker Desktop is running (check the taskbar icon)

**Port 8501 already in use**
→ Another Streamlit is running. Kill it: `pkill -f streamlit` or restart Docker

**Package missing inside container**
→ Add it to the `Dockerfile` RUN pip install line, then rebuild the container
