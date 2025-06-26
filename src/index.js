#!/usr/bin/env node

/**
 * Insight Digger MCP Bridge
 * 
 * This bridge connects Claude Desktop to the enterprise Insight Digger MCP system.
 * It preserves all sophisticated caching, workflow guidance, and session management
 * while providing standard MCP protocol compliance.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

/**
 * Bridge Session Management
 * Single session design as per requirements
 */
class BridgeSession {
  constructor() {
    this.sessionId = uuidv4();
    this.authenticated = false;
    this.mcpClientUrl = null;
    this.availableTools = [];
    this.workflowGuidance = null;
    this.apiUrl = null;
    this.jwtToken = null;
  }

  /**
   * Initialize session with your existing MCP Client Flask API
   */
  async initialize(apiUrl, jwtToken, mcpClientUrl) {
    try {
      // Validate inputs
      if (!apiUrl || !jwtToken || !mcpClientUrl) {
        throw new Error("Missing required parameters: apiUrl, jwtToken, or mcpClientUrl");
      }

      // Test if MCP Client is reachable
      try {
        await axios.get(`${mcpClientUrl}/health`, { timeout: 5000 });
      } catch (error) {
        throw new Error(`Cannot reach MCP Client at ${mcpClientUrl}. Please ensure the Insight Digger MCP Client service is running.`);
      }

      this.mcpClientUrl = mcpClientUrl;
      this.apiUrl = apiUrl;
      this.jwtToken = jwtToken;

      // Call your existing /init endpoint
      await axios.post(`${mcpClientUrl}/init`, {
        session_id: this.sessionId,
        apiUrl: apiUrl,
        jwtToken: jwtToken
      }, { timeout: 10000 });

      // Get available tools and workflow guidance from your existing /tools endpoint
      const toolsResponse = await axios.post(`${mcpClientUrl}/tools`, {
        session_id: this.sessionId
      }, { timeout: 10000 });
      
      // Store all tools and workflow guidance exactly as returned by your system
      this.availableTools = toolsResponse.data.tools || [];
      this.workflowGuidance = toolsResponse.data.workflow_guidance || {};
      this.authenticated = true;

      console.error(`[BRIDGE] Session ${this.sessionId} initialized successfully with ${this.availableTools.length} tools`);
      
    } catch (error) {
      console.error(`[BRIDGE] Session initialization failed: ${error.message}`);
      if (error.response && error.response.status === 400) {
        throw new Error(`Authentication failed: Invalid API URL or JWT token. Please check your credentials.`);
      }
      throw error;
    }
  }

  /**
   * Call tool through your existing MCP Client Flask API
   * Preserves ALL caching and parameter injection logic
   */
  async callTool(toolName, args) {
    if (!this.authenticated) {
      throw new Error('Session not authenticated. Please call setup_authentication first.');
    }

    try {
      // Forward directly to your existing Flask API /call-tool endpoint
      const payload = {
        session_id: this.sessionId,
        tool: toolName,
        params: args || {}
      };
      
      const response = await axios.post(`${this.mcpClientUrl}/call-tool`, payload, {
        timeout: 300000 // 5 minutes for long-running analysis
      });
      
      return response.data; // Your caching logic is preserved!
      
    } catch (error) {
      console.error(`[BRIDGE] Tool call failed for ${toolName}:`, error.message);
      if (error.response && error.response.status === 409) {
        throw new Error('Session expired or invalid. Please re-authenticate.');
      }
      if (error.response && error.response.data && error.response.data.error) {
        throw new Error(error.response.data.error);
      }
      throw error;
    }
  }

  /**
   * Cleanup session
   */
  async shutdown() {
    if (this.authenticated && this.mcpClientUrl) {
      try {
        await axios.post(`${this.mcpClientUrl}/shutdown`, {
          session_id: this.sessionId
        }, { timeout: 5000 });
        console.error(`[BRIDGE] Session ${this.sessionId} shut down`);
      } catch (error) {
        console.error(`[BRIDGE] Error during shutdown: ${error.message}`);
      }
    }
    this.authenticated = false;
  }
}

// Global session instance (single session design)
const bridgeSession = new BridgeSession();

/**
 * MCP Server Setup
 */
const server = new Server(
  {
    name: "insight-digger-mcp-bridge",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

/**
 * Authentication Tool - MUST be called first
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === "setup_authentication") {
    try {
      const { apiUrl, jwtToken, mcpClientUrl } = args;
      
      // Default MCP Client URL if not provided
      const clientUrl = mcpClientUrl || process.env.MCP_CLIENT_URL || "https://your-mcp-client.com";
      
      await bridgeSession.initialize(apiUrl, jwtToken, clientUrl);
      
      return {
        content: [
          {
            type: "text",
            text: `✅ Authentication successful! Connected to Insight Digger with ${bridgeSession.availableTools.length} analysis tools available.\n\nYou can now start your data analysis. I recommend beginning with 'list_sources' to see available data sources.`
          }
        ]
      };
    } catch (error) {
      return {
        content: [
          {
            type: "text",
            text: `❌ Authentication failed: ${error.message}`
          }
        ],
        isError: true
      };
    }
  }

  // All other tools - proxy to your existing system
  try {
    const result = await bridgeSession.callTool(name, args);
    
    // Transform result to MCP format if needed
    if (typeof result === 'string') {
      return {
        content: [{ type: "text", text: result }]
      };
    }
    
    if (result && typeof result === 'object') {
      // Handle your existing response format
      if (result.summary && result.dashboardUrl) {
        // Final analysis results
        return {
          content: [
            {
              type: "text", 
              text: `## Analysis Results\n\n${result.summary}\n\n🔗 **Interactive Dashboard:** ${result.dashboardUrl}\n\nYou can now:\n- Explore the interactive dashboard\n- Ask follow-up questions\n- Request additional analysis\n- Modify charts in the dashboard and ask me to reanalyze`
            }
          ]
        };
      } else if (result.markdownConfig) {
        // Configuration review step
        return {
          content: [
            {
              type: "text",
              text: `## Analysis Configuration\n\nI've prepared the following analysis configuration:\n\n${result.markdownConfig}\n\nDoes this configuration look correct for your analysis? You can:\n- Approve it as-is (I'll proceed with execution)\n- Request modifications\n- Ask questions about any part`
            }
          ]
        };
      } else if (result.data && Array.isArray(result.data)) {
        // Source listing or similar
        const count = result.count || result.data.length;
        const sources = result.data.map(source => 
          `- **${source.title}** (ID: ${source.id})\n  Type: ${source.type}, Columns: ${source.numberOfColumns}, Updated: ${source.updated}`
        ).join('\n');
        
        return {
          content: [
            {
              type: "text",
              text: `## Available Data Sources (${count} found)\n\n${sources}\n\nPlease select a source by specifying its **ID** for analysis.`
            }
          ]
        };
      } else if (result.error) {
        // Error from your system
        return {
          content: [
            {
              type: "text",
              text: `❌ Error: ${result.error}`
            }
          ],
          isError: true
        };
      }
    }
    
    // Fallback - return as formatted JSON
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
    
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `❌ Error executing ${name}: ${error.message}`
        }
      ],
      isError: true
    };
  }
});

/**
 * Dynamic Tool Registration
 * Returns setup_authentication + all tools from your existing system
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  const tools = [
    {
      name: "setup_authentication",
      description: "🔐 Setup authentication credentials for Insight Digger. **Call this FIRST** before any data analysis. Provide your API URL and JWT token to establish a secure connection to the enterprise data platform.",
      inputSchema: {
        type: "object",
        properties: {
          apiUrl: {
            type: "string",
            description: "The base URL of your Insight Digger backend API (e.g., https://your-platform.com/api)"
          },
          jwtToken: {
            type: "string", 
            description: "Your JWT authentication token (14-day validity)"
          },
          mcpClientUrl: {
            type: "string",
            description: "MCP Client service URL (optional, defaults to environment variable MCP_CLIENT_URL)"
          }
        },
        required: ["apiUrl", "jwtToken"]
      }
    }
  ];

  // Add all tools from your existing system after authentication
  if (bridgeSession.authenticated) {
    tools.push(...bridgeSession.availableTools);
    
    // Enhance tool descriptions with workflow context if available
    if (bridgeSession.workflowGuidance && bridgeSession.workflowGuidance.workflow) {
      const workflowSteps = bridgeSession.workflowGuidance.workflow.steps || [];
      tools.forEach(tool => {
        const step = workflowSteps.find(s => s.tool === tool.name || (s.tools && s.tools.includes(tool.name)));
        if (step) {
          tool.description = `**Step ${step.step}: ${step.description}** - ${tool.description}\n\n*Guidance: ${step.guidance}*`;
        }
      });
    }
  }

  return { tools };
});

/**
 * Cleanup on exit
 */
process.on('SIGINT', async () => {
  console.error('[BRIDGE] Shutting down...');
  await bridgeSession.shutdown();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.error('[BRIDGE] Shutting down...');
  await bridgeSession.shutdown();
  process.exit(0);
});

/**
 * Start the bridge server
 */
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('[BRIDGE] Insight Digger MCP Bridge started successfully');
}

main().catch((error) => {
  console.error('[BRIDGE] Fatal error:', error);
  process.exit(1);
}); 