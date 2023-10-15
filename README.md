<style>
   .image-link-container {
      display: flex;
      flex-direction: row;
      gap: 10px;
      flex-wrap: wrap;
   }
   .image-link {
      display: flex;
      justify-content: center;
      align-items: center;
      background-color: #fff;
      width: 100px;
      padding: 5px;
      border-radius: 5px;
   }  
</style>

# 🏋🏿‍♂️ rezervo

[![rezervo](https://img.shields.io/badge/ghcr.io-mathiazom%2Frezervo-blue?logo=docker)](https://github.com/users/mathiazom/packages/container/package/rezervo)

Automatic booking of group classes.

### ⚙️ Providers
<div class="image-link-container">
   <a href="https://www.ibooking.no" class="image-link">
      <img src="./assets/providers/ibooking.png" alt="ibooking" height="30">
   </a>
   <a href="https://www.brpsystems.com" class="image-link">
      <img src="./assets/providers/brpsystems.png" alt="brpsystems" height="30">
   </a>
</div>

### 🤸 Integrations
<div class="image-link-container">
   <a href="https://www.sit.no" class="image-link">
      <img src="./assets/integrations/sit.svg" alt="sit" height="30">
   </a>
   <a href="https://www.fsc.no" class="image-link">
      <img src="./assets/integrations/fsc.svg" alt="fsc" height="30">
   </a>
   <a href="https://www.3t.no" class="image-link">
      <img src="./assets/integrations/3t.png" alt="3t" height="30">
   </a>
</div>


### 🧑‍💻 Development

#### 🐍 Setup Python environment
1. Ensure Python 3.10+ is installed
2. Install dependencies using Poetry (install from https://python-poetry.org/docs/#installation)
    ```shell
    poetry install
    ```
3. In the [`rezervo`](rezervo) directory, define `.env` and `config.json` based on [`.env.template`](rezervo/.env.template) and [`config.template.json`](rezervo/config.template.json). This includes defining Auth0 tenant details, credentials for Slack notifications and app-wide booking preferences.
   
   <details>
      <summary>📳 Web Push variables</summary>
   
      ##### Web Push variables
      Web push requires a VAPID key pair. This can be generated with the following command using `openssl`:
      ```shell
      openssl ecparam -name prime256v1 -genkey -noout -out vapid_keypair.pem
      ```
      The private key can then be encoded as base64 and added to the `.env` file as `WEB_PUSH_PRIVATE_KEY`:
      ```shell
      openssl ec -in ./vapid_keypair.pem -outform DER|tail -c +8|head -c 32|base64|tr -d '=' |tr '/+' '_-' >> vapid_private.txt
      ```
      Similarly, the public key can be encoded as base64 and included in the client application receiving the notifications:
      ```shell
      openssl ec -in ./vapid_keypair.pem -pubout -outform DER|tail -c 65|base64|tr -d '=' |tr '/+' '_-'|tr -d '\n' >> vapid_public.txt
      ```
   </details>


#### 🐋 Run with Docker
1. Make sure you have defined `.env` and `config.json` as described above
2. With [docker](https://docs.docker.com/get-docker/) and [docker compose](https://docs.docker.com/compose/) installed, run
    ```shell
    docker compose -f docker/docker-compose.dev.yml up -d --build
    ```
3. Within the container, explore available cli commands
    ```shell
    rezervo --help
    ```

#### 🧹 Format and lint
```shell
poe fix
```

#### 🔌 Support new integration
Add your own integration by implementing the [`Integration`](rezervo/integrations/integration.py) interface. Then, include it `ACTIVE_INTEGRATIONS` in [`rezervo/integrations/active.py`](rezervo/integrations/active.py).

### 🚀 Deployment
A template for a production deployment is given in [`docker-compose.template.yml`](docker/docker-compose.template.yml), which uses the most recent [`rezervo` Docker image](https://github.com/users/mathiazom/packages/container/package/sit-rezervo).
