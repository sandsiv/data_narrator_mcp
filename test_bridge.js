#!/usr/bin/env node

/**
 * Simple test script for the MCP Bridge
 * This helps validate the bridge functionality during development
 */

import { spawn } from 'child_process';
import { createReadStream } from 'fs';

async function testBridge() {
  console.log('🧪 Testing MCP Bridge...\n');

  // Start the bridge process
  const bridge = spawn('node', ['src/index.js'], {
    stdio: ['pipe', 'pipe', 'inherit']
  });

  // Test sequence
  const testSequence = [
    // Initialize
    {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "test-client", version: "1.0.0" }
      }
    },
    // List tools (should show only setup_authentication initially)
    {
      jsonrpc: "2.0",
      id: 2,
      method: "tools/list",
      params: {}
    },
    // Test authentication (will fail without real credentials)
    {
      jsonrpc: "2.0",
      id: 3,
      method: "tools/call",
      params: {
        name: "setup_authentication",
        arguments: {
          apiUrl: "https://test-api.com",
          jwtToken: "test-token",
          mcpClientUrl: "http://localhost:5000"
        }
      }
    }
  ];

  let testIndex = 0;

  // Send test messages
  function sendNextTest() {
    if (testIndex < testSequence.length) {
      const test = testSequence[testIndex];
      console.log(`📤 Sending test ${testIndex + 1}:`, JSON.stringify(test, null, 2));
      bridge.stdin.write(JSON.stringify(test) + '\n');
      testIndex++;
    } else {
      console.log('\n✅ All tests sent. Terminating bridge...');
      bridge.kill('SIGTERM');
    }
  }

  // Handle responses
  let buffer = '';
  bridge.stdout.on('data', (data) => {
    buffer += data.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep incomplete line in buffer

    lines.forEach(line => {
      if (line.trim()) {
        try {
          const response = JSON.parse(line);
          console.log(`📥 Response ${response.id}:`, JSON.stringify(response, null, 2));
          console.log('---');
          
          // Send next test after receiving response
          setTimeout(sendNextTest, 1000);
        } catch (e) {
          console.log('📝 Bridge output:', line);
        }
      }
    });
  });

  bridge.on('close', (code) => {
    console.log(`\n🏁 Bridge test completed with exit code ${code}`);
  });

  bridge.on('error', (error) => {
    console.error('❌ Bridge error:', error);
  });

  // Start the test sequence
  setTimeout(sendNextTest, 1000);
}

// Run the test
testBridge().catch(console.error); 