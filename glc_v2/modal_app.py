"""
Modal deployment wrapper for glc_v1  (Session 12, Move 1: wrap the gateway).
"""

from pathlib import Path
import modal

app = modal.App("glc-v1-gateway")
LOCAL_GLC = Path(__file__).parent / "glc"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libseccomp2")
    .pip_install(
        "fastapi>=0.110",
        "uvicorn[standard]>=0.27",
        "httpx>=0.27",
        "python-dotenv>=1.0",
        "pydantic>=2.6",
        "jsonschema>=4.21",
        "pyyaml>=6.0",
        "websockets>=12.0",
        "twilio>=9.0",
    )
    .run_commands("useradd -m appuser")
    .run_commands('echo "su - appuser" >> /root/.bashrc')
    .run_commands('echo "export PYTHONPATH=/app" >> /home/appuser/.bashrc')
    .run_commands('echo "export PYTHONSTARTUP=/app/glc/security/sandbox.py" >> /home/appuser/.bashrc')
    .env({"GLC_CONFIG_DIR": "/data/glc", "GLC_ENV": "production", "PYTHONPATH": "/app", "PYTHONSTARTUP": "/app/glc/security/sandbox.py"})
    .add_local_dir(str(LOCAL_GLC), remote_path="/app/glc")
)

data_volume = modal.Volume.from_name("glc-data", create_if_missing=True)
llm_secret = modal.Secret.from_name("glc-llm-keys")
install_secret = modal.Secret.from_name("glc-install-token")

@app.function(
    image=image,
    volumes={"/data": data_volume},
    secrets=[llm_secret, install_secret],
    min_containers=0,
)
@modal.asgi_app()
def fastapi_app():
    import os
    os.makedirs("/data/glc", exist_ok=True)
    from glc.security.sandbox import apply_sandbox
    apply_sandbox()
    from glc.main import app as web
    return web

@app.function(
    image=image,
    secrets=[llm_secret],
    min_containers=0,
)
def policy_engine(tool_call: dict, context: dict):
    from glc.security.sandbox import apply_sandbox
    apply_sandbox()
    from glc.policy.engine import evaluate
    return evaluate(tool_call, context)

from glc.channels import registry
for channel_name in registry.list_channels():
    def make_adapter(name: str):
        secret = modal.Secret.from_name(f"glc-{name}-keys")
        
        @app.function(
            image=image,
            secrets=[secret, install_secret],
            min_containers=0,
            name=f"{name}_adapter",
            serialized=True,
        )
        @modal.asgi_app()
        def adapter_func():
            from glc.security.sandbox import apply_sandbox
            apply_sandbox()
            from glc.channels.adapter_app import create_adapter_app
            return create_adapter_app(name)
            
    make_adapter(channel_name)
