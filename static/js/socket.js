// Setup Socket.IO connection
const socket = io();

// Handle connection events
socket.on('connect', () => {
    console.log('Connected to server');
    socket.emit('request_all_channels'); // Request the current state of all channels
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
});

socket.on('reconnect', () => {
    console.log('Reconnected to server');
    socket.emit('request_all_channels'); // Request fresh data after reconnection
});

// Handle channel updates
socket.on('update_channel', (data) => {
    if (typeof handleChannelUpdate === 'function') {
        handleChannelUpdate(data);
    }
});

// Handle new channel creation
socket.on('new_channel', (data) => {
    if (typeof handleNewChannel === 'function') {
        handleNewChannel(data);
    }
});

// Handle channel deletion
socket.on('delete_channel', (data) => {
    if (typeof handleChannelDeletion === 'function') {
        handleChannelDeletion(data);
    }
});

// Handle global updates
socket.on('update_all_channels', () => {
    if (typeof handleGlobalUpdate === 'function') {
        handleGlobalUpdate();
    }
});