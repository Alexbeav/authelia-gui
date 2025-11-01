# Deployment Guide for Synology NAS

## Overview
This guide explains how to deploy the Authelia User Management GUI on your Synology NAS using Container Manager.

## Prerequisites
- Synology DSM 7.0 or later
- Container Manager package installed
- Authelia already running on the NAS

## Method 1: Using Synology Container Manager (Recommended)

### Step 1: Build the Docker Image

Since we can't build directly via SSH, we have two options:

#### Option A: Build via Synology Task Scheduler
1. Open **Control Panel** > **Task Scheduler**
2. Create a **User-defined script** task:
   - User: root
   - Script:
     ```bash
     cd /volume1/docker/identity
     docker build -t authelia-gui:latest ./authelia-gui
     ```
3. Run the task once to build the image

#### Option B: Build on Another Machine
1. On a machine with Docker installed:
   ```bash
   # Copy the authelia-gui folder
   scp -r ulduar:/volume1/docker/identity/authelia-gui ./

   # Build the image
   cd authelia-gui
   docker build -t authelia-gui:latest .

   # Save the image
   docker save authelia-gui:latest | gzip > authelia-gui.tar.gz

   # Copy to NAS
   scp authelia-gui.tar.gz ulduar:/volume1/docker/

   # On NAS, load the image (via SSH or Task Scheduler)
   docker load < /volume1/docker/authelia-gui.tar.gz
   ```

### Step 2: Create Container in Container Manager

1. Open **Container Manager** app on Synology
2. Go to **Container** tab
3. Click **Create** button
4. Select **authelia-gui:latest** from the image dropdown
5. Click **Next** and configure:

   **Container Name**: `authelia-gui`

   **Port Settings**:
   - Local Port: `8080` → Container Port: `8080`

   **Volume Settings** (click Advanced Settings):
   - Mount Path: `/volume1/docker/identity/authelia/config`
   - Mount Point in Container: `/config`
   - Read-only: ✓ (checked)

   **Environment Variables**:
   - `AUTHELIA_CONFIG_PATH` = `/config`

   **Network**: Same network as Authelia (if using custom network)

6. Click **Apply** and start the container

### Step 3: Access the GUI

Open your browser and navigate to:
```
http://your-nas-ip:8080
```

You should see the Authelia User Management dashboard!

## Method 2: Quick Test with Python (No Docker)

If you want to test quickly without Docker:

1. SSH into your NAS
2. Install Python packages (if pip is available):
   ```bash
   cd /volume1/docker/identity/authelia-gui
   pip3 install -r requirements.txt --user
   ```

3. Run the application:
   ```bash
   cd /volume1/docker/identity/authelia-gui/app
   AUTHELIA_CONFIG_PATH=/volume1/docker/identity/authelia/config \
   python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
   ```

4. Access at `http://your-nas-ip:8080`

**Note**: This method is for testing only. Docker deployment is recommended for production.

## Troubleshooting

### Container won't start
- Check logs in Container Manager
- Verify volume mount points are correct
- Ensure port 8080 is not already in use

### "No users found" error
- Verify `/config` volume is correctly mounted
- Check that `users.yml` exists at `/config/users.yml`
- Check container logs for permission errors

### Database errors
- Verify `db.sqlite3` exists at `/config/db.sqlite3`
- Check file permissions (should be readable by container)

### Connection refused
- Verify container is running
- Check port mapping is correct (8080:8080)
- Ensure firewall allows port 8080

## Security Recommendations

### For Testing
The GUI is currently open to anyone who can access port 8080. For testing on a local network, this is acceptable.

### For Production (Phase 4)
We will add:
1. Authelia authentication (protect the GUI with Authelia itself)
2. Traefik reverse proxy integration
3. HTTPS support
4. Access control rules

## Next Steps

Once the GUI is running:
1. Verify all users are displayed correctly
2. Check that 2FA status is accurate
3. Click on a user to view detailed information
4. Check authentication logs

If everything works, we can proceed to Phase 2 (user creation)!
