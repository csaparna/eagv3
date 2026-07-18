import modal
app = modal.App.lookup("glc-v1-gateway")
@app.local_entrypoint()
def main():
    pass
