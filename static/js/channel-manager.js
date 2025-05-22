// Channel management and WebSocket communication

// Socket.io connection
const socket = io({
    reconnectionDelay: 1000,        // Start with 1s delay
    reconnectionDelayMax: 5000,     // Maximum delay between reconnections
    randomizationFactor: 0.5,       // Add randomization to the delay
    timeout: 20000,                 // Longer connection timeout
    reconnectionAttempts: 10        // Limit reconnection attempts
});

// Channel data from server
window.channelData = {};

// Debounce function to prevent too many requests
function debounce(func, wait) {
    let timeout;
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

// Connect to WebSocket server
socket.on('connect', () => {
    console.log('Connected to server');
    
    // Request the current state of all channels when connected
    // Use setTimeout to delay the request slightly and avoid race conditions
    setTimeout(() => {
        socket.emit('request_all_channels');
    }, 500);
});

// Add reconnection handling
socket.on('disconnect', () => {
    console.log('Disconnected from server');
});

// Debounce the reconnection event to prevent rapid reconnections
const debouncedReconnect = debounce(() => {
    console.log('Reconnected to server');
    // Request fresh data after reconnection with a small delay
    setTimeout(() => {
        socket.emit('request_all_channels');
    }, 1000);
}, 2000);

socket.on('reconnect', debouncedReconnect);

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

// Add error handling for socket.io errors
socket.on('error', (error) => {
    console.error('Socket.io connection error:', error);
});

socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
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

// Handle global updates with debounce to prevent spamming the server
const handleGlobalUpdate = debounce(() => {
    socket.emit('request_all_channels'); // Request fresh state for all channels
}, 1000);

window.socket = socket; // Expose socket globally for other modules
window.handleChannelUpdate = handleChannelUpdate; // Expose function globally
window.handleNewChannel = handleNewChannel; // Expose function globally
window.handleChannelDeletion = handleChannelDeletion; // Expose function globally
window.handleGlobalUpdate = handleGlobalUpdate; // Expose function globally