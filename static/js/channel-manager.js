// Channel management and WebSocket communication

// Socket.io connection
const socket = io();

// Channel data from server
window.channelData = {};

// Connect to WebSocket server
socket.on('connect', () => {
    console.log('Connected to server');
    
    // Request the current state of all channels when connected
    socket.emit('request_all_channels');
});

// Add reconnection handling
socket.on('disconnect', () => {
    console.log('Disconnected from server');
});

socket.on('reconnect', () => {
    console.log('Reconnected to server');
    // Request fresh data after reconnection
    socket.emit('request_all_channels');
});

// Listen for channel updates
socket.on('update_channel', function(data) {
    handleChannelUpdate(data);
});

// Listen for new channel creation
socket.on('new_channel', function(data) {
    handleNewChannel(data);
});

// Listen for channel deletion
socket.on('delete_channel', function(data) {
    handleChannelDeletion(data);
});

function handleChannelUpdate(data) {
    // Initialize the channel if it doesn't exist yet
    if (!channelData[data.channel]) {
        channelData[data.channel] = {};
    }
    
    // Update the specific channel that changed
    channelData[data.channel] = { 
        ...channelData[data.channel], 
        ...data 
    };
    
    // Update physics info since data changed
    updatePhysicsInfo();
}

function handleNewChannel(data) {
    // Add the new channel to our data
    channelData[data.channel] = data;
    updatePhysicsInfo();
}

function handleChannelDeletion(data) {
    if (channelData[data.channel]) {
        delete channelData[data.channel];
        updatePhysicsInfo();
    }
}

function handleGlobalUpdate() {
    socket.emit('request_all_channels'); // Request fresh state for all channels
}
window.socket = socket; // Expose socket globally for other modules
window.handleChannelUpdate = handleChannelUpdate; // Expose function globally
window.handleNewChannel = handleNewChannel; // Expose function globally
window.handleChannelDeletion = handleChannelDeletion; // Expose function globally
window.handleGlobalUpdate = handleGlobalUpdate; // Expose function globally