// Connect to WebSocket server
const socket = io();
let channels = {};

// Handle connection events
socket.on('connect', function() {
    console.log('Connected to server');
    // Request all channels when we connect
    socket.emit('request_all_channels');
});

socket.on('disconnect', function() {
    console.log('Disconnected from server');
});

// Handle channel data updates
socket.on('all_channels', function(data) {
    channels = data;
    updateChannelsUI();
});

socket.on('update_channel', function(data) {
    channels[data.channel] = {...channels[data.channel], ...data};
    updateChannelUI(data.channel);
});

socket.on('new_channel', function(data) {
    channels[data.channel] = data;
    addChannelToUI(data.channel);
});

socket.on('delete_channel', function(data) {
    delete channels[data.channel];
    removeChannelFromUI(data.channel);
});

// UI Functions
function updateChannelsUI() {
    // Clear existing UI
    const container = document.getElementById('channels-container');
    container.innerHTML = '';
    
    // Add UI for each channel
    for (const channel in channels) {
        addChannelToUI(channel);
    }
}

function addChannelToUI(channelId) {
    const channel = channels[channelId];
    const container = document.getElementById('channels-container');
    
    // Create channel element if it doesn't exist
    let channelElement = document.getElementById(`channel-${channelId}`);
    if (!channelElement) {
        channelElement = document.createElement('div');
        channelElement.id = `channel-${channelId}`;
        channelElement.className = 'channel';
        if (channel.mute) {
            channelElement.classList.add('muted');
        }
        
        container.appendChild(channelElement);
    }
    
    // Set channel content
    channelElement.innerHTML = `
        <h2>Channel ${channelId}</h2>
        <div class="control">
            <label for="frequency-${channelId}">Frequency:</label>
            <input type="range" id="frequency-${channelId}" min="20" max="5000" step="1" 
                value="${channel.frequency || 440}" 
                oninput="updateFrequencyValue(${channelId}, this.value)">
            <span id="frequency-value-${channelId}">${channel.frequency || 440} Hz</span>
        </div>
        <div class="control">
            <label for="volume-${channelId}">Volume:</label>
            <input type="range" id="volume-${channelId}" min="0" max="1" step="0.01"
                value="${channel.volume || 0.5}"
                oninput="updateVolumeValue(${channelId}, this.value)">
            <span id="volume-value-${channelId}">${(channel.volume || 0.5) * 100}%</span>
        </div>
        <div class="channel-controls">
            <button class="mute-button" onclick="toggleMute(${channelId})">
                ${channel.mute ? 'Unmute' : 'Mute'}
            </button>
            <button class="delete-button" onclick="deleteChannel(${channelId})">Delete Channel</button>
        </div>
    `;
}

function updateChannelUI(channelId) {
    const channel = channels[channelId];
    if (!channel) return;
    
    // Update frequency slider
    const freqSlider = document.getElementById(`frequency-${channelId}`);
    const freqValue = document.getElementById(`frequency-value-${channelId}`);
    if (freqSlider && freqValue) {
        freqSlider.value = channel.frequency;
        freqValue.textContent = `${channel.frequency} Hz`;
    }
    
    // Update volume slider
    const volSlider = document.getElementById(`volume-${channelId}`);
    const volValue = document.getElementById(`volume-value-${channelId}`);
    if (volSlider && volValue) {
        volSlider.value = channel.volume;
        volValue.textContent = `${(channel.volume * 100).toFixed(0)}%`;
    }
    
    // Update mute button and class
    const channelElement = document.getElementById(`channel-${channelId}`);
    const muteButton = channelElement.querySelector('.mute-button');
    
    if (muteButton) {
        muteButton.textContent = channel.mute ? 'Unmute' : 'Mute';
    }
    
    if (channelElement) {
        if (channel.mute) {
            channelElement.classList.add('muted');
        } else {
            channelElement.classList.remove('muted');
        }
    }
}

function removeChannelFromUI(channelId) {
    const channelElement = document.getElementById(`channel-${channelId}`);
    if (channelElement) {
        channelElement.remove();
    }
}

// User interaction handlers
function updateFrequencyValue(channelId, value) {
    const frequency = parseFloat(value);
    document.getElementById(`frequency-value-${channelId}`).textContent = `${frequency} Hz`;
    
    // Send update to server
    socket.emit('change_frequency', {
        channel: channelId,
        frequency: frequency
    });
}

function updateVolumeValue(channelId, value) {
    const volume = parseFloat(value);
    document.getElementById(`volume-value-${channelId}`).textContent = `${(volume * 100).toFixed(0)}%`;
    
    // Send update to server
    socket.emit('change_volume', {
        channel: channelId,
        volume: volume
    });
}

function toggleMute(channelId) {
    const channel = channels[channelId];
    const newMuteState = !channel.mute;
    
    // Send update to server
    socket.emit('toggle_mute', {
        channel: channelId,
        mute: newMuteState
    });
}

function deleteChannel(channelId) {
    if (confirm(`Are you sure you want to delete Channel ${channelId}?`)) {
        // Send delete request to server
        socket.emit('delete_channel', {
            channel: channelId
        });
    }
}

// Button handlers
document.getElementById('addChannelBtn').addEventListener('click', function() {
    // Request a new channel from the server
    socket.emit('new_channel');
});

document.getElementById('visualizationBtn').addEventListener('click', function() {
    window.location.href = '/visualization';
});
