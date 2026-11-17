\# Defect Detection App (Roboflow + FastAPI)



Upload a product image, such as fabric or a shoe, and get the defects back:

\- \*\*Actual image\*\* and \*\*predicted image\*\* side by side, with boxes and labels drawn on the predicted image

\- A defect table showing the type, confidence, position and size of each defect

\- Several \*\*profiles\*\* (for example Fabric, Shoe), each with its own Roboflow API key and model, which you switch from the UI

\- Every result saved to disk (original image, predicted image and JSON)



Works with Roboflow \*\*object detection\*\*, \*\*instance segmentation\*\* and \*\*classification\*\* models.



\---



\## 1. Requirements

| Item | Details |

|---|---|

| OS | Windows 10/11 (macOS and Linux also work) |

| Python | \*\*3.9 or newer\*\* (3.14 works) |

| Internet | Required, because every detection is sent to Roboflow's cloud |

| Roboflow account | Free account at https://app.roboflow.com, plus your \*\*Private API key\*\* |



\---



\## 2. Project structure

```

fabric-defect-api/

├── main.py              ← the API (FastAPI)

├── static/

│   ├── index.html       ← inspection page (actual vs predicted)

│   └── settings.html    ← settings page (profiles, API key, model)

├── samples/             ← sample fabric images for testing

├── requirements.txt     ← Python libraries

├── .env.example         ← template for the first profile

├── run\_windows.bat      ← one-click setup and start (Windows)

├── run\_mac\_linux.sh     ← one-click setup and start (Mac/Linux)

├── README.md

│

├── .env                 ← (created by you) first API key + model

├── settings.json        ← (auto-created) all profiles, including API keys

├── .venv/               ← (auto-created) Python virtual environment

└── outputs/             ← (auto-created) saved results

&#x20;   ├── original/        ← images as uploaded

&#x20;   ├── predicted/       ← images with boxes drawn

&#x20;   └── results/         ← one JSON file per image

```



\---



\## 3. First-time setup (Windows)



\### Step 1: Install Python

1\. Download Python from https://www.python.org/downloads/

2\. While installing, \*\*tick "Add python.exe to PATH"\*\*, then click \*\*Install Now\*\*.

3\. Check that it worked. Open \*\*cmd\*\* and run:

&#x20;  ```cmd

&#x20;  python --version

&#x20;  ```



\### Step 2: Open cmd in the project folder

Open the `fabric-defect-api` folder in File Explorer, click the address bar, type `cmd` and press \*\*Enter\*\*.



\### Step 3: Create the virtual environment and install the libraries

```cmd

python -m venv .venv

.venv\\Scripts\\activate

python -m pip install --upgrade pip

pip install -r requirements.txt

```

The command line should now start with `(.venv)`.



> If you copied the project from another PC, \*\*delete the old `.venv` folder first\*\*. A venv doesn't work after being moved to another computer.



\### Step 4: Create the `.env` file

```cmd

copy .env.example .env

notepad .env

```

Fill it in, then save:

```

ROBOFLOW\_API\_KEY=your\_private\_api\_key

MODEL\_ID=yolo-fabric-defect-detector/1

ROBOFLOW\_API\_URL=https://serverless.roboflow.com

CONFIDENCE=0.4

```

To get your API key, go to \*\*app.roboflow.com → Settings → API Keys → copy the Private API Key\*\*.



> `.env` is only used on the \*\*first start\*\*, to create the first profile. After that, manage keys and models on the \*\*Settings page\*\*.



\### Step 5: Start the server

```cmd

uvicorn main:app --host 127.0.0.1 --port 8000

```

Wait until you see:

```

Uvicorn running on http://127.0.0.1:8000

Application startup complete.

```

\*\*Keep this window open.\*\* Closing it stops the app.



\### Step 6: Open the app

Go to \*\*http://127.0.0.1:8000\*\* in Chrome or Edge.



> \*\*Shortcut:\*\* instead of steps 3–5, double-click `run\_windows.bat`. On the first run it installs everything and opens `.env` in Notepad. Add your key, save, and double-click it again.



\---



\## 4. Daily use

1\. Open cmd in the project folder.

2\. Run:

&#x20;  ```cmd

&#x20;  .venv\\Scripts\\activate

&#x20;  uvicorn main:app --host 127.0.0.1 --port 8000

&#x20;  ```

3\. Open http://127.0.0.1:8000

4\. To stop the server, press \*\*Ctrl+C\*\* in the cmd window.



\### Optional: start with a double-click

Create a file called `start\_server.bat` in the project folder:

```bat

@echo off

cd /d %\~dp0

call .venv\\Scripts\\activate

uvicorn main:app --host 127.0.0.1 --port 8000

pause

```



\### Optional: start automatically when Windows starts

1\. Press \*\*Win+R\*\*, type `shell:startup` and press \*\*Enter\*\*.

2\. Put a \*\*shortcut\*\* to `start\_server.bat` in the folder that opens.



\---



\## 5. Using the app



\### Inspection page (`/ui`)

1\. Choose the product from the \*\*dropdown\*\* at the top right (Fabric, Shoe…).

2\. Click or drag an image into the upload box (JPG, PNG or WEBP, up to 10 MB).

3\. Set the \*\*Confidence\*\* slider. Detections below this level are hidden. Try 20–30% if nothing is found.

4\. Click \*\*Detect defects\*\*.

5\. Check the results:

&#x20;  - \*\*Actual image\*\* and \*\*predicted image\*\* side by side. Click an image to view it full size.

&#x20;  - A \*\*summary\*\*, for example "2 defects found: hole, oil\_spot".

&#x20;  - A \*\*table\*\* showing the defect type, confidence, centre (x, y) and size (w × h).

&#x20;  - \*\*History\*\*, where you can click a past result to view it again.



\### Settings page (`/ui/settings`, or the \*\*⚙ Settings\*\* button)

| Field | What to enter |

|---|---|

| Roboflow Model ID | `project-name/version`, for example `footwear-o7gku/8` |

| Display name | Fills in automatically (Fabric, Shoe…) and can be edited |

| Page title | Fills in automatically, for example "Shoe Defect Inspection" |

| API key | Your Roboflow key. \*\*Leave it blank\*\* to keep the current key, or to reuse the active profile's key for a new profile. |

| Default confidence | Slider from 5% to 95% |

| API URL | Leave as `https://serverless.roboflow.com` |



Buttons:

\- \*\*Test connection\*\*: checks the key and model before saving

\- \*\*Save\*\* / \*\*Save \& use this profile\*\*

\- On each profile card: \*\*Use\*\*, \*\*Edit\*\*, \*\*Test\*\*, \*\*Delete\*\*



\### Example: adding a Shoe profile

1\. Open \*\*Settings\*\* and type the model ID `footwear-o7gku/8`.

2\. Change the display name to \*\*Shoe\*\*.

3\. Click \*\*Test connection\*\*. You should see ✔.

4\. Click \*\*Save \& use this profile\*\*.

5\. Go back to the inspection page. The title now reads \*\*"Shoe Defect Inspection"\*\*.



\---



\## 6. Models



\### Fabric

| Model ID | Classes | Notes |

|---|---|---|

| `yolo-fabric-defect-detector/1` | defect, hole, objects, oil\_spot, thread\_error | \*\*Recommended.\*\* Its page reports 97.9% mAP@50 on its own test set. |

| `fabric-defect-aqnck/1` | Defect | Weaker: 58% mAP and a single general label |



\### Shoe (public models; all small, so test them before relying on them)

| Model ID | Type | Classes |

|---|---|---|

| `footwear-o7gku/8` | Detection | broken, external, skip |

| `shoe-inspector/1` | Detection | accepted, unaccepted |

| `shoe-dirt-detection-t8bnd/4` | Segmentation | clean\_shoe, dirty\_light, dirty\_medium, dirty\_heavy |

| `shoe-defect-classification/3` | Classification | Cracks, Scratches, Sole\_detachment (one label for the whole image) |



You can find more models at https://universe.roboflow.com. For production, train your own model on 200–500 labelled photos from your line.



\---



\## 7. Saved results

Every detection creates three files with the same name:

```

outputs\\original\\20261117\_143000\_shoe\_img1\_ab12cd.jpg

outputs\\predicted\\20261117\_143000\_shoe\_img1\_ab12cd\_predicted.jpg

outputs\\results\\20261117\_143000\_shoe\_img1\_ab12cd.json

```

You can delete old files from `outputs\\` at any time.



\---



\## 8. API endpoints (for integration)

Interactive docs: \*\*http://127.0.0.1:8000/docs\*\*



| Method | Endpoint | Purpose |

|---|---|---|

| GET | `/health` | Status and active profile |

| POST | `/detect` | Upload `file` and get JSON with defects and image URLs. Optional: `?confidence=0.3`, `?include\_base64=true` |

| POST | `/detect/image` | Upload `file` and get the predicted JPEG directly |

| GET | `/history` | Past results. Optional: `?limit=50`, `?profile\_id=shoe` |

| GET | `/settings` | All profiles (keys masked) |

| POST | `/settings/profiles` | Create or update a profile (JSON) |

| POST | `/settings/active` | Switch profile: `{"id": "shoe"}` |

| DELETE | `/settings/profiles/{id}` | Delete a profile |

| POST | `/settings/test` | Test a key and model |



Example (cmd):

```cmd

curl.exe -X POST "http://127.0.0.1:8000/detect?confidence=0.3" -F "file=@samples\\model2\_sample\_01.jpg"

curl.exe -X POST "http://127.0.0.1:8000/detect/image" -F "file=@samples\\model2\_sample\_01.jpg" -o result.jpg

```



Example (Python):

```python

import requests

with open("samples/model2\_sample\_01.jpg", "rb") as f:

&#x20;   r = requests.post("http://127.0.0.1:8000/detect", files={"file": ("img.jpg", f, "image/jpeg")})

print(r.json())

```



\---



\## 9. Access from other PCs on the network (optional)

1\. Start the server with `--host 0.0.0.0`:

&#x20;  ```cmd

&#x20;  uvicorn main:app --host 0.0.0.0 --port 8000

&#x20;  ```

2\. Allow the port through Windows Firewall. Open cmd \*\*as Administrator\*\* and run:

&#x20;  ```cmd

&#x20;  netsh advfirewall firewall add rule name="Defect API" dir=in action=allow protocol=TCP localport=8000

&#x20;  ```

3\. Find this PC's IP with `ipconfig` (look for the \*\*IPv4 Address\*\*).

4\. On the other PC, open `http://<that-ip>:8000`, for example `http://192.168.1.25:8000`.



> ⚠ The app has \*\*no login\*\*. Anyone who can open the page can change the settings. Use it only on a trusted office network, never expose it to the internet.



\---



\## 10. macOS / Linux

```bash

cd fabric-defect-api

python3 -m venv .venv

source .venv/bin/activate

pip install --upgrade pip

pip install -r requirements.txt

cp .env.example .env          # edit it: open -e .env (Mac) or nano .env

uvicorn main:app --host 127.0.0.1 --port 8000

```

Or run `chmod +x run\_mac\_linux.sh \&\& ./run\_mac\_linux.sh`.



\---



\## 11. Troubleshooting

| Problem | Fix |

|---|---|

| `'python' is not recognized` | Reinstall Python with \*\*Add to PATH\*\* ticked, then reopen cmd |

| `No module named ...` | Activate the venv first: `.venv\\Scripts\\activate` |

| Yellow bar: "No Roboflow API key" | Add the key on the \*\*Settings\*\* page |

| `Cloud inference failed: HTTP 401/403` | Wrong API key. Copy it again from Roboflow. |

| `Cloud inference failed: HTTP 404` | Wrong model ID or version. Check it on Roboflow Universe. |

| `Cloud inference failed: HTTP 429` | Out of credits or rate-limited. Check usage on Roboflow. |

| Result always shows 0 defects | Lower the confidence slider, use a clearer close-up photo, or try a different model |

| `{"detail":"Not Found"}` | Wrong URL. Use http://127.0.0.1:8000 |

| Port 8000 already in use | Close the other server window, or use `--port 8001` |

| Other PCs can't connect | Use `--host 0.0.0.0`, add the firewall rule, and check both PCs are on the same network |

| Page shows an old design after an update | Press \*\*Ctrl+F5\*\* to refresh |

| Copied `.venv` gives errors | Delete `.venv` and repeat Step 3 |



\---



\## 12. Updating the code

1\. Stop the server with \*\*Ctrl+C\*\*.

2\. Replace `main.py` and the files in `static\\`.

3\. \*\*Keep\*\* `.env`, `settings.json`, `.venv\\` and `outputs\\`. They hold your keys, profiles and results.

4\. If `requirements.txt` changed, run `pip install -r requirements.txt`.

5\. Start the server again and press \*\*Ctrl+F5\*\* in the browser.



\---



\## 13. Security notes

\- `.env` and `settings.json` contain your \*\*Roboflow API keys\*\*. Don't share them or commit them to git (they're already in `.gitignore`).

\- If a key leaks, generate a new one in Roboflow (\*\*Settings → API Keys\*\*) and update it on the Settings page.

\- Each detection uses Roboflow credits. Check your usage at app.roboflow.com.

