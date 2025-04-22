document.addEventListener('DOMContentLoaded', function() {
    // Check chain validity
    fetch('/api/chain_verify')
        .then(response => response.json())
        .then(data => {
            const statusElement = document.getElementById('chain-status');
            if (data.valid) {
                statusElement.textContent = 'Chain Status: ✅ Valid';
                statusElement.classList.add('valid');
            } else {
                statusElement.textContent = 'Chain Status: ❌ Invalid';
                statusElement.classList.add('invalid');
            }
        });
    
    // Load brain info
    fetch('/api/brain')
        .then(response => response.json())
        .then(data => {
            const brainInfo = document.getElementById('brain-info');
            brainInfo.innerHTML = `
                <p><strong>XP:</strong> ${data.xp || 0}</p>
                <p><strong>Level:</strong> ${Math.floor((data.xp || 0) / 100) + 1}</p>
                <p><strong>Mode:</strong> ${data.mode || 'Standard'}</p>
                <p><strong>Memory Entries:</strong> ${data.memory_count || 0}</p>
            `;
        });
    
    // Load memory entries
    fetch('/api/memory')
        .then(response => response.json())
        .then(data => {
            const memoryEntries = document.getElementById('memory-entries');
            if (data.length === 0) {
                memoryEntries.innerHTML = '<p class="text-muted">No memory entries yet.</p>';
                return;
            }
            
            memoryEntries.innerHTML = '';
            data.slice(-20).reverse().forEach(entry => {
                const entryDiv = document.createElement('div');
                entryDiv.className = 'memory-entry';
                entryDiv.textContent = entry;
                memoryEntries.appendChild(entryDiv);
            });
        });
    
    // Handle memory query
    document.getElementById('query-button').addEventListener('click', function() {
        const query = document.getElementById('query-input').value.trim();
        if (!query) return;
        
        const resultsDiv = document.getElementById('query-results');
        resultsDiv.innerHTML = '<p class="text-center">Searching...</p>';
        
        fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        })
        .then(response => response.json())
        .then(data => {
            resultsDiv.innerHTML = '';
            if (data.length === 0) {
                resultsDiv.innerHTML = '<p class="text-center text-muted">No results found.</p>';
                return;
            }
            
            data.forEach(result => {
                const resultDiv = document.createElement('div');
                resultDiv.className = 'query-result';
                resultDiv.innerHTML = `
                    <div class="score">Relevance: ${(result.score * 100).toFixed(1)}%</div>
                    <div class="content">${result.content}</div>
                `;
                resultsDiv.appendChild(resultDiv);
            });
        });
    });
    
    // Handle plugin form submission
    document.getElementById('plugin-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const plugin = document.getElementById('plugin-select').value;
        const target = document.getElementById('target-input').value;
        
        fetch('/api/run_plugin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ plugin: plugin, target: target })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
                return;
            }
            
            alert('Plugin executed successfully!');
            // Refresh memory entries
            fetch('/api/memory')
                .then(response => response.json())
                .then(memData => {
                    const memoryEntries = document.getElementById('memory-entries');
                    memoryEntries.innerHTML = '';
                    memData.slice(-20).reverse().forEach(entry => {
                        const entryDiv = document.createElement('div');
                        entryDiv.className = 'memory-entry';
                        entryDiv.textContent = entry;
                        memoryEntries.appendChild(entryDiv);
                    });
                });
        });
    });
    
    // Add Enter key support for query
    document.getElementById('query-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('query-button').click();
        }
    });
});
