# HeatWave
![HeatWave](https://github.com/user-attachments/assets/cc2b636b-b5e5-4601-9374-6c418216f138)

## Description
HeatWave is a MIDI controller application that allows you to generate and control 8 audio frequencies and volumes using MIDI messages. You can record settings and then travel through past saved settings via the channel log.

## Installation
1. Clone the repository:
    ```sh
    git clone <repository-url>
    cd <repository-directory>
    ```

2. Create a virtual environment:
    ```sh
    python3 -m venv myenv
    source myenv/bin/activate  # On Windows use `myenv\Scripts\activate`
    ```

3. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Usage
1. Ensure your MIDI device is connected and recognized by the system.

2. Run the main application:
    ```sh
    python3 main.py
    ```

3. The application will start and continuously read MIDI input. Use your MIDI controller to send messages and control the audio.

4. Access the web interface for additional controls and visualization:
   - Open a web browser and navigate to `http://localhost:6134` (or the configured port)
   - The web interface provides real-time visualization of audio frequencies
   - Use the web controls to adjust settings and monitor the system remotely
   - Frequency and volume changes will be reflected in both the MIDI controller lights and web visualization

5. Press Ctrl+C to stop the application.

6. The state of the channels will be logged in [channel_log.jsonl](http://_vscodecontentref_/1).

## Contributing
This is unlikely to apply to anyone, but hey, if you've got ideas for adding a compressor or making a different control system, I'm totally interested. My goal is to be able to control fire as pixels via fourier transforms.
