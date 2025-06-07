// MCP Code Repository Q&A JavaScript

// Main variables
const API_URL = window.location.origin;
let connectionStatus, statusText, question, repoPath, loading, resultContainer, answerElement;

// Initialize when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    connectionStatus = document.getElementById('connectionStatus');
    statusText = document.getElementById('statusText');
    question = document.getElementById('question');
    repoPath = document.getElementById('repoPath');
    loading = document.getElementById('loading');
    resultContainer = document.getElementById('resultContainer');
    answerElement = document.getElementById('answer');
    
    // Initialize components
    checkServer();
    setupEventListeners();
    setupSampleQuestions();
    
    // Setup markdown renderer
    marked.setOptions({
        // Preserve HTML in markdown content
        breaks: true,
        gfm: true,
        headerIds: true,
        mangle: false,
        sanitize: false,
        silent: true
    });
});

// Check if server is running
async function checkServer() {
    try {
        const response = await fetch(`${API_URL}/.well-known/mcp`);
        if (response.ok) {
            connectionStatus.classList.add('connected');
            statusText.textContent = 'MCP server connected';
            
            // Try to get repository path from server
            try {
                const resourcesResponse = await fetch(`${API_URL}/list_resources`);
                if (resourcesResponse.ok) {
                    const data = await resourcesResponse.json();
                    if (data.resources && data.resources.length > 0 && data.resources[0].metadata.repo_path) {
                        repoPath.value = data.resources[0].metadata.repo_path;
                    }
                }
            } catch (e) {
                console.error("Could not get repository path:", e);
            }
        } else {
            connectionStatus.classList.remove('connected');
            statusText.textContent = 'Server Disconnected';
        }
    } catch (e) {
        connectionStatus.classList.remove('connected');
        statusText.textContent = 'Server Disconnected';
        console.error("Could not connect to server:", e);
    }
}

// Set up event listeners
function setupEventListeners() {
    // Enter key in question field
    question.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Prevent default to avoid newline
            submitQuestion(e);
        }
    });
    
    // Make example repository paths clickable
    document.querySelectorAll('.example-path').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            repoPath.value = this.textContent;
        });
    });
    
    // Make sample questions clickable
    document.querySelectorAll('.sample-question-list div').forEach(item => {
        item.addEventListener('click', function() {
            question.value = this.textContent;
            question.focus();
            
            // Find the closest repo-path-note and extract the path
            const repoSection = this.closest('.col-md-6');
            if (repoSection) {
                const pathNote = repoSection.querySelector('.repo-path-note code');
                if (pathNote) {
                    repoPath.value = pathNote.textContent;
                }
            }
        });
        
        // Add cursor pointer style
        item.style.cursor = 'pointer';
    });
}

// Sample questions are now just for display
function setupSampleQuestions() {
    // No click functionality needed
}

// Submit question to server
async function submitQuestion() {
    if (!question.value.trim()) {
        return;
    }
    
    loading.style.display = 'block';
    resultContainer.style.display = 'none';
    
    try {
        console.log('Sending question:', question.value);
        const response = await fetch(`${API_URL}/question`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question.value,
                repo_path: repoPath.value
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('Received response:', data);
            
            if (data && data.content) {
                console.log('Rendering content...');
                answerElement.innerHTML = marked.parse(data.content);
                resultContainer.style.display = 'block';
                
                // Process rendered content after a small delay
                setTimeout(processRenderedContent, 100);
            } else {
                showError('Response was successful but no content was received');
                console.error('No content in response:', data);
            }
        } else {
            let errorText = 'Error: ' + response.status + ' ' + response.statusText;
            try {
                const errorData = await response.json();
                if (errorData.error) {
                    errorText += ' - ' + errorData.error;
                }
            } catch (e) {
                // Could not parse error response as JSON
            }
            showError(errorText);
            console.error('Error response:', response);
        }
    } catch (e) {
        showError('Error: ' + e.message);
        console.error('Request error:', e);
    } finally {
        loading.style.display = 'none';
    }
}

// Process rendered content to prepare for Prism highlighting
function processRenderedContent() {
    console.log('Processing rendered content...');
    
    // We're now relying on standard HTML <details> and <summary> for code expansion
    // Add proper language classes for code blocks
    document.querySelectorAll('pre code').forEach(block => {
        // Add language class if not already present
        if (!block.classList.contains('language-python')) {
            block.classList.add('language-python');
        }
    });
    
    // Re-highlight all code blocks with Prism
    if (window.Prism) {
        Prism.highlightAll();
    }
    
    // Add additional class to code blocks after details for better spacing
    document.querySelectorAll('details + pre').forEach(block => {
        block.classList.add('mt-4');
    });
}


// Show error message
function showError(message) {
    answerElement.innerHTML = `<div class="alert alert-danger">${message}</div>`;
    resultContainer.style.display = 'block';
}
