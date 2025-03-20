#!/usr/bin/env python3
import argparse
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Headless Agent - Fake Video</title>
    <!-- Load external_api.min.js from the Flask static folder -->
    <script src="http://127.0.0.1:5000/static/jitsi-meet/external_api.min.js"></script>
    <script>
      function debugLog(...args) {
        var msg = args.join(" ");
        console.log(msg);
        var img = new Image();
        img.src = "http://127.0.0.1:5000/api/remote_log?message=" + encodeURIComponent(msg);
      }
      
      window.addEventListener("load", function(){
        debugLog("Window loaded, external_api.min.js should be available.");
      });
      
      const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = function(constraints) {
        debugLog("getUserMedia override called with:", JSON.stringify(constraints));
        if (constraints && constraints.video) {
          debugLog("Creating fake video track from static image...");
          const canvas = document.createElement("canvas");
          canvas.width = 640;
          canvas.height = 480;
          const ctx = canvas.getContext("2d");
          const img = new Image();
          // Use agent avatar from local static folder
          img.src = "http://127.0.0.1:5000/static/images/agents/" + agentName.toLowerCase() + ".png";
          return new Promise((resolve, reject) => {
            img.onload = function() {
              ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
              const stream = canvas.captureStream(5);
              debugLog("Fake canvas stream created for agent:", agentName);
              resolve(stream);
            };
            img.onerror = function(err) {
              debugLog("Error loading image for fake video:", err);
              reject(err);
            };
          });
        } else {
          debugLog("No video requested, calling original getUserMedia...");
          return originalGetUserMedia(constraints);
        }
      };
    </script>
  </head>
  <body style="margin:0; padding:0;">
    <div id="agent-jitsi" style="width:100vw; height:100vh;"></div>
    <script>
      const domain = "127.0.0.1:5000";
      const roomName = "__ROOM__";
      const agentName = "__AGENT__";
      
      debugLog("Starting initialization for agent", agentName, "in room", roomName);
      
      const options = {
        roomName: roomName,
        parentNode: document.getElementById("agent-jitsi"),
        width: "100%",
        height: "100%",
        userInfo: {
          displayName: agentName,
          avatarUrl: "http://127.0.0.1:5000/static/images/agents/" + agentName.toLowerCase() + ".png"
        },
        configOverwrite: {
          prejoinPageEnabled: false,
          defaultLanguage: "en",
          startWithAudioMuted: true,
          startWithVideoMuted: false,
          disableAudioLevels: true
        },
        interfaceConfigOverwrite: {
          TOOLBAR_BUTTONS: ["microphone", "camera", "hangup", "chat", "participants-pane", "tileview"],
          DEFAULT_AVATAR_URL: "http://127.0.0.1:5000/static/images/agents/" + agentName.toLowerCase() + ".png"
        }
      };
      
      try {
        debugLog("Creating JitsiMeetExternalAPI instance...");
        const api = new JitsiMeetExternalAPI(domain, options);
        debugLog("JitsiMeetExternalAPI instance created for agent", agentName);
      
        api.addEventListener("videoConferenceJoined", function(e) {
          debugLog("videoConferenceJoined event received for", agentName, ":", JSON.stringify(e));
          setTimeout(() => {
            debugLog("Attempting to send chat message from agent", agentName);
            try {
              api.executeCommand("sendEndpointTextMessage", "", "Hello from " + agentName);
              debugLog("Chat message sent from agent", agentName);
            } catch (err) {
              debugLog("Error sending chat message from agent", agentName, err);
            }
          }, 5000);
        });
      
        api.addEventListener("errorOccurred", function(e) {
          debugLog("Error occurred for agent", agentName, ":", JSON.stringify(e));
        });
      } catch (err) {
        debugLog("Exception during initialization for agent", agentName, ":", err);
      }
    </script>
  </body>
</html>
"""

def main(room, agent):
    filename = f"temp_{room}_{agent}.html"
    with open(filename, "w") as f:
        f.write(HTML_TEMPLATE.replace("__ROOM__", room).replace("__AGENT__", agent))
    
    chrome_options = Options()
    # For testing, you might disable headless mode
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--window-size=1280,800")
    chrome_options.add_argument("--use-fake-ui-for-media-stream")
    chrome_options.add_argument("--use-fake-device-for-media-stream")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-software-rasterizer")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    file_path = os.path.abspath(filename)
    driver.get("file://" + file_path)
    print(f"Agent {agent} joined room {room} in browser.")
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Shutting down agent", agent)
    finally:
        driver.quit()
        os.remove(filename)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--room", required=True, help="The Jitsi room name")
    parser.add_argument("--agent", required=True, help="Agent display name")
    args = parser.parse_args()
    main(args.room, args.agent)