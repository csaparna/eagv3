import modal
import time

app = modal.App("test-sandbox-port")

@app.local_entrypoint()
def main():
    sandbox = modal.Sandbox.create(
        "python", "-m", "http.server", "8000",
        encrypted_ports=[8000],
        app=app,
    )
    print("Sandbox created.")
    print("Tunnels:", sandbox.tunnels)
    time.sleep(5)
    sandbox.terminate()

