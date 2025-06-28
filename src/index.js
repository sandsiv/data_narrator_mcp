#!/usr/bin/env node

/**
 * Insight Digger MCP Bridge
 * 
 * A lightweight bridge that translates between standard MCP protocol 
 * and the existing enterprise-grade MCP Client Flask API.
 * 
 * This preserves all existing functionality:
 * - JWT authentication and session management
 * - Intelligent parameter caching and injection
 * - Multi-step workflow optimization
 * - Enterprise security and compliance features
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

// Configuration
const MCP_CLIENT_URL = process.env.MCP_CLIENT_URL || 'http://127.0.0.1:33000';
const ENABLE_LOGGING = process.env.BRIDGE_LOGGING !== 'false'; // Default enabled, set BRIDGE_LOGGING=false to disable
const DEBUG_LEVEL = process.env.BRIDGE_DEBUG === 'true'; // Set BRIDGE_DEBUG=true for full request/response bodies
const LOGS_DIR = './logs';

// Bridge session state
let bridgeSession = {
  sessionId: null,
  authenticated: false,
  availableTools: [],
  workflowGuidance: null
};

// Cache for /tools-schema response (never changes)
let cachedToolsSchema = null;

// Create MCP server
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
 * Simple logging function to track requests and responses
 */
function logToFile(type, data) {
  if (!ENABLE_LOGGING) return;
  
  try {
    // Ensure logs directory exists
    if (!existsSync(LOGS_DIR)) {
      mkdirSync(LOGS_DIR, { recursive: true });
    }
    
    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      type,
      sessionId: bridgeSession.sessionId,
      debugLevel: DEBUG_LEVEL,
      data
    };
    
    // Create filename with date and debug suffix
    const date = timestamp.split('T')[0];
    const debugSuffix = DEBUG_LEVEL ? '-debug' : '';
    const logFile = join(LOGS_DIR, `bridge-${date}${debugSuffix}.log`);
    
    // Append log entry
    const logLine = JSON.stringify(logEntry, null, DEBUG_LEVEL ? 2 : 0) + '\n';
    writeFileSync(logFile, logLine, { flag: 'a' });
    
  } catch (error) {
    console.error(`[BRIDGE] Logging failed:`, error.message);
  }
}

/**
 * Helper function to safely serialize data for logging
 */
function safeSerialize(data, maskSensitive = true) {
  if (!data) return data;
  
  try {
    // Deep clone to avoid modifying original
    const cloned = JSON.parse(JSON.stringify(data));
    
    if (maskSensitive && typeof cloned === 'object') {
      // Mask sensitive fields
      if (cloned.jwtToken) {
        cloned.jwtToken = `***${cloned.jwtToken.slice(-4)}`;
      }
      if (cloned.apiUrl && cloned.apiUrl.includes('@')) {
        cloned.apiUrl = cloned.apiUrl.replace(/\/\/.*@/, '//***@');
      }
    }
    
    return cloned;
  } catch (error) {
    return '[Serialization Error]';
  }
}

/**
 * Generate unique session ID for this bridge instance
 */
function generateSessionId() {
  return `bridge-${uuidv4()}`;
}

/**
 * Setup authentication with the existing MCP client
 */
async function setupAuthentication(args) {
  const { apiUrl, jwtToken } = args;
  
  // Log authentication request
  if (DEBUG_LEVEL) {
    logToFile('auth_request_debug', { 
      fullRequest: safeSerialize({ apiUrl, jwtToken }, true),
      timestamp: new Date().toISOString()
    });
  } else {
    logToFile('auth_request', { 
      apiUrl: apiUrl ? apiUrl.replace(/\/\/.*@/, '//***@') : null,
      hasJwtToken: !!jwtToken 
    });
  }
  
  if (!apiUrl || !jwtToken) {
    throw new Error("Both apiUrl and jwtToken are required");
  }

  // Generate session ID for this bridge instance
  bridgeSession.sessionId = generateSessionId();
  
  try {
    // Initialize session with existing MCP client
    console.error(`[BRIDGE] Initializing session ${bridgeSession.sessionId} with MCP client`);
    const initPayload = {
      session_id: bridgeSession.sessionId,
      apiUrl: apiUrl,
      jwtToken: jwtToken
    };
    
    if (DEBUG_LEVEL) {
      logToFile('flask_init_request', { 
        url: `${MCP_CLIENT_URL}/init`,
        payload: safeSerialize(initPayload, true)
      });
    }
    
    const initResponse = await axios.post(`${MCP_CLIENT_URL}/init`, initPayload);
    
    if (DEBUG_LEVEL) {
      logToFile('flask_init_response', { 
        status: initResponse.status,
        data: initResponse.data
      });
    }

    // Get available tools from existing MCP client
    console.error(`[BRIDGE] Fetching available tools for session ${bridgeSession.sessionId}`);
    const toolsPayload = { session_id: bridgeSession.sessionId };
    
    if (DEBUG_LEVEL) {
      logToFile('flask_tools_request', { 
        url: `${MCP_CLIENT_URL}/tools`,
        payload: toolsPayload
      });
    }
    
    const toolsResponse = await axios.post(`${MCP_CLIENT_URL}/tools`, toolsPayload);
    
    if (DEBUG_LEVEL) {
      logToFile('flask_tools_response', { 
        status: toolsResponse.status,
        toolCount: toolsResponse.data.tools?.length || 0,
        fullResponse: toolsResponse.data
      });
    }

    // Store tools and workflow guidance for dynamic registration
    bridgeSession.availableTools = toolsResponse.data.tools || [];
    bridgeSession.workflowGuidance = toolsResponse.data.workflow_guidance;
    bridgeSession.authenticated = true;

    console.error(`[BRIDGE] Authentication successful. ${bridgeSession.availableTools.length} tools available.`);

    const result = {
      status: "success",
      message: `Authentication successful! ${bridgeSession.availableTools.length} analysis tools are now available.`,
      sessionId: bridgeSession.sessionId
    };
    
    // Log authentication success
    if (DEBUG_LEVEL) {
      logToFile('auth_success_debug', { 
        fullResult: result,
        availableTools: bridgeSession.availableTools.map(t => ({ name: t.name, description: t.description?.substring(0, 100) + '...' })),
        workflowGuidance: bridgeSession.workflowGuidance
      });
    } else {
      logToFile('auth_success', { 
        toolsCount: bridgeSession.availableTools.length,
        sessionId: result.sessionId 
      });
    }
    
    return result;

  } catch (error) {
    console.error(`[BRIDGE] Authentication failed:`, error.message);
    
    // Log authentication failure
    logToFile('auth_error', { 
      error: error.message,
      statusCode: error.response?.status 
    });
    
    // Reset session state on failure
    bridgeSession = {
      sessionId: null,
      authenticated: false,
      availableTools: [],
      workflowGuidance: null
    };

    throw new Error(`Authentication failed: ${error.response?.data?.error || error.message}`);
  }
}

/**
 * Proxy tool call to existing MCP client (preserves all caching logic)
 */
async function proxyToolCall(toolName, args) {
  if (!bridgeSession.authenticated) {
    throw new Error("Authentication required. Please call setup_authentication first.");
  }

  // Log tool call request
  if (DEBUG_LEVEL) {
    logToFile('tool_request_debug', { 
      tool: toolName,
      fullArgs: safeSerialize(args, false), // Don't mask tool args in debug mode
      timestamp: new Date().toISOString()
    });
  } else {
    logToFile('tool_request', { 
      tool: toolName, 
      hasArgs: !!args && Object.keys(args).length > 0,
      argKeys: args ? Object.keys(args) : []
    });
  }

  try {
    console.error(`[BRIDGE] Proxying tool call: ${toolName}`);
    
    const requestPayload = {
      session_id: bridgeSession.sessionId,
      tool: toolName,
      params: args || {}
    };
    
    if (DEBUG_LEVEL) {
      logToFile('flask_tool_request', { 
        url: `${MCP_CLIENT_URL}/call-tool`,
        payload: safeSerialize(requestPayload, false)
      });
    }
    
    const response = await axios.post(`${MCP_CLIENT_URL}/call-tool`, requestPayload);

    // Log tool call success
    if (DEBUG_LEVEL) {
      logToFile('flask_tool_response', { 
        tool: toolName,
        status: response.status,
        fullResponse: response.data
      });
    } else {
      logToFile('tool_success', { 
        tool: toolName,
        status: response.data.status,
        hasData: !!response.data && Object.keys(response.data).length > 0
      });
    }

    return response.data;

  } catch (error) {
    console.error(`[BRIDGE] Tool call failed for ${toolName}:`, error.message);
    
    // Log tool call error
    logToFile('tool_error', { 
      tool: toolName,
      error: error.message,
      statusCode: error.response?.status
    });
    
    throw new Error(`Tool execution failed: ${error.response?.data?.error || error.message}`);
  }
}

/**
 * Get tools schema from Flask API (cached forever)
 */
async function getToolsSchema() {
  if (cachedToolsSchema) {
    if (DEBUG_LEVEL) {
      logToFile('tools_schema_cached', { purpose: 'Using cached tools schema' });
    }
    return cachedToolsSchema;
  }
  
  try {
    console.error(`[BRIDGE] Fetching tools schema from /tools-schema`);
    
    if (DEBUG_LEVEL) {
      logToFile('tools_schema_request', { 
        url: `${MCP_CLIENT_URL}/tools-schema`,
        purpose: 'Fetching tools schema (will be cached forever)'
      });
    }
    
    const response = await axios.get(`${MCP_CLIENT_URL}/tools-schema`);
    cachedToolsSchema = response.data;
    
    if (DEBUG_LEVEL) {
      logToFile('tools_schema_response', { 
        status: response.status,
        hasSystemInfo: !!cachedToolsSchema.system_info,
        toolsCount: cachedToolsSchema.tools?.length || 0,
        cached: true
      });
    }
    
    return cachedToolsSchema;
  } catch (error) {
    console.error(`[BRIDGE] Failed to fetch tools schema:`, error.message);
    
    if (DEBUG_LEVEL) {
      logToFile('tools_schema_error', { 
        error: error.message,
        url: `${MCP_CLIENT_URL}/tools-schema`
      });
    }
    
    return { system_info: null, tools: [] };
  }
}

/**
 * Create enhanced authentication tool description with system context
 */
async function createAuthenticationTool() {
  const schema = await getToolsSchema();
  const systemInfo = schema.system_info;
  
  let description = 'Setup authentication credentials for Sandsiv+ Insight Digger. This must be called FIRST before any analysis tools become available. Requires your API URL and JWT token.';
  
  if (systemInfo) {
    description += `\n\n**About This System:**\n`;
    description += `- **System**: ${systemInfo.system_name} (${systemInfo.system_type})\n`;
    description += `- **Purpose**: ${systemInfo.purpose}\n`;
    
    if (systemInfo.when_to_use && systemInfo.when_to_use.length > 0) {
      description += `\n**When to Use This System:**\n`;
      systemInfo.when_to_use.forEach(use => {
        description += `- ${use}\n`;
      });
    }
    
    if (systemInfo.capabilities && systemInfo.capabilities.length > 0) {
      description += `\n**Capabilities:**\n`;
      systemInfo.capabilities.forEach(capability => {
        description += `- ${capability}\n`;
      });
    }
    
    if (systemInfo.workflow_overview) {
      description += `\n**Workflow**: ${systemInfo.workflow_overview}`;
    }
  }

  return {
    name: 'setup_authentication',
    description: description,
    inputSchema: {
      type: 'object',
      properties: {
        apiUrl: {
          type: 'string',
          description: 'Your Sandsiv+ API base URL (e.g., https://your-domain.sandsiv.com)'
        },
        jwtToken: {
          type: 'string',
          description: 'Your JWT authentication token for the Sandsiv+ platform'
        }
      },
      required: ['apiUrl', 'jwtToken']
    }
  };
}

/**
 * Enhance tool descriptions with workflow guidance after authentication
 */
function enhanceToolsWithWorkflowGuidance(tools) {
  if (!bridgeSession.workflowGuidance?.workflow) {
    if (DEBUG_LEVEL) {
      logToFile('workflow_enhancement_skipped', { 
        reason: 'No workflow guidance available',
        toolsCount: tools.length,
        hasWorkflowGuidance: !!bridgeSession.workflowGuidance,
        hasWorkflow: !!bridgeSession.workflowGuidance?.workflow
      });
    }
    return tools;
  }

  const workflow = bridgeSession.workflowGuidance.workflow;
  
  if (DEBUG_LEVEL) {
    logToFile('workflow_enhancement_start', { 
      toolsCount: tools.length,
      workflowSteps: workflow.recommended_workflow?.steps?.length || 0,
      workflowNotes: workflow.important_notes?.length || 0,
      workflowData: workflow
    });
  }
  
  // Create comprehensive workflow description
  let workflowDescription = `\n\n**📋 RECOMMENDED WORKFLOW**\n`;
  workflowDescription += `${workflow.recommended_workflow?.description || ''}\n\n`;
  
  if (workflow.recommended_workflow?.steps) {
    workflow.recommended_workflow.steps.forEach(step => {
      workflowDescription += `**Step ${step.step}: ${step.description}**\n`;
      workflowDescription += `- Tool: \`${step.tool}\`\n`;
      workflowDescription += `- Guidance: ${step.guidance}\n\n`;
    });
  }
  
  if (workflow.important_notes && workflow.important_notes.length > 0) {
    workflowDescription += `**⚠️ IMPORTANT NOTES:**\n`;
    workflow.important_notes.forEach(note => {
      workflowDescription += `- ${note}\n`;
    });
  }

  // Add workflow guidance to the first analysis tool's description
  const enhancedTools = tools.map(tool => {
    // Add to the first non-auth tool (typically list_sources)
    if (tool.name !== 'setup_authentication' && tool === tools.find(t => t.name !== 'setup_authentication')) {
      const enhancedTool = {
        ...tool,
        description: tool.description + workflowDescription
      };
      
      if (DEBUG_LEVEL) {
        logToFile('workflow_enhancement_applied', { 
          toolName: tool.name,
          originalDescriptionLength: tool.description.length,
          workflowDescriptionLength: workflowDescription.length,
          enhancedDescriptionLength: enhancedTool.description.length,
          workflowContent: workflowDescription
        });
      }
      
      return enhancedTool;
    }
    return tool;
  });

  if (DEBUG_LEVEL) {
    logToFile('workflow_enhancement_complete', { 
      originalToolsCount: tools.length,
      enhancedToolsCount: enhancedTools.length,
      toolsWithEnhancement: enhancedTools.filter(t => t.description.includes('📋 RECOMMENDED WORKFLOW')).length
    });
  }

  return enhancedTools;
}

/**
 * Get all available tools (including unauthenticated ones marked as requiring auth)
 */
async function getAllAvailableTools() {
  const schema = await getToolsSchema();
  return schema.tools || [];
}

/**
 * List available tools (proactive approach - show all tools, mark unauthenticated ones)
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  // Log tools list request
  logToFile('list_tools_request', { 
    authenticated: bridgeSession.authenticated,
    availableToolsCount: bridgeSession.availableTools.length 
  });

  // Create authentication tool with enhanced description
  const authTool = await createAuthenticationTool();
  const tools = [authTool];

  if (bridgeSession.authenticated && bridgeSession.availableTools.length > 0) {
    // User is authenticated - show enhanced tools with workflow guidance
    const rawTools = [...bridgeSession.availableTools];
    
    if (DEBUG_LEVEL) {
      logToFile('tools_enhancement_start', { 
        rawToolsCount: rawTools.length,
        rawToolNames: rawTools.map(t => t.name),
        hasWorkflowGuidance: !!bridgeSession.workflowGuidance
      });
    }
    
    // Enhance tools with detailed workflow guidance
    const enhancedTools = enhanceToolsWithWorkflowGuidance(rawTools);
    
    tools.push(...enhancedTools);
  } else {
    // User is not authenticated - show all tools but mark them as requiring authentication
    const allTools = await getAllAvailableTools();
    
    if (allTools.length > 0) {
      const unauthenticatedTools = allTools.map(tool => {
        // Remove null annotations to avoid MCP SDK validation errors
        const cleanTool = { ...tool };
        if (cleanTool.annotations === null) {
          delete cleanTool.annotations;
        }
        
        return {
          ...cleanTool,
          description: `🔒 **[Requires Authentication]** ${cleanTool.description}\n\n⚠️ **Please authenticate first** by calling the \`setup_authentication\` tool above. This tool will become fully functional after authentication.`
        };
      });
      
      if (DEBUG_LEVEL) {
        logToFile('unauthenticated_tools_shown', { 
          toolsCount: unauthenticatedTools.length,
          toolNames: unauthenticatedTools.map(t => t.name)
        });
      }
      
      tools.push(...unauthenticatedTools);
    }
  }

  // Log tools list response
  if (DEBUG_LEVEL) {
    logToFile('list_tools_response_debug', { 
      toolCount: tools.length,
      toolNames: tools.map(t => t.name),
      authenticated: bridgeSession.authenticated,
      fullTools: tools.map(t => ({
        name: t.name,
        descriptionLength: t.description.length,
        hasWorkflowGuidance: t.description.includes('📋 RECOMMENDED WORKFLOW'),
        hasSystemInfo: t.description.includes('About This System'),
        requiresAuth: t.description.includes('🔒 **[Requires Authentication]**'),
        description: t.description // Full description for debugging
      }))
    });
  } else {
    logToFile('list_tools_response', { 
      toolCount: tools.length,
      toolNames: tools.map(t => t.name),
      authenticated: bridgeSession.authenticated
    });
  }

  return { tools };
});

/**
 * Handle tool calls
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  // Log incoming tool call
  if (DEBUG_LEVEL) {
    logToFile('mcp_tool_call_debug', { 
      tool: name,
      fullRequest: { name, arguments: safeSerialize(args, name === 'setup_authentication') },
      timestamp: new Date().toISOString()
    });
  } else {
    logToFile('mcp_tool_call', { 
      tool: name,
      hasArgs: !!args && Object.keys(args).length > 0,
      argKeys: args ? Object.keys(args) : []
    });
  }

    try {
    if (name === 'setup_authentication') {
      const result = await setupAuthentication(args);
      
      // Log MCP response
      if (DEBUG_LEVEL) {
        logToFile('mcp_response_debug', { 
          tool: name,
          fullResponse: result,
          success: true
        });
      } else {
        logToFile('mcp_response', { 
          tool: name,
          status: result.status,
          success: true
        });
      }
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }
        ]
      };
    } else if (!bridgeSession.authenticated) {
      // Handle calls to unauthenticated tools
      const authRequiredResponse = {
        status: 'error',
        error: `Authentication required. Please call 'setup_authentication' first to access the '${name}' tool.`,
        toolRequested: name,
        authenticationNeeded: true
      };
      
      if (DEBUG_LEVEL) {
        logToFile('mcp_auth_required', { 
          tool: name,
          response: authRequiredResponse
        });
      }
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(authRequiredResponse, null, 2)
          }
        ]
      };
    } else {
      // Proxy authenticated tool calls to existing MCP client
      const result = await proxyToolCall(name, args);
      
      // Log MCP response
      if (DEBUG_LEVEL) {
        logToFile('mcp_response_debug', { 
          tool: name,
          fullResponse: result,
          success: true
        });
      } else {
        logToFile('mcp_response', { 
          tool: name,
          status: result.status,
          success: true
        });
      }
      
        return {
          content: [
            {
            type: 'text',
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
    }
  } catch (error) {
    // Log MCP error response
    logToFile('mcp_error', { 
      tool: name,
      error: error.message,
      success: false
    });
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            status: 'error',
            error: error.message
          }, null, 2)
        }
      ],
      isError: true
    };
  }
});

/**
 * Cleanup on shutdown
 */
async function cleanup() {
  if (bridgeSession.authenticated && bridgeSession.sessionId) {
    try {
      console.error(`[BRIDGE] Cleaning up session ${bridgeSession.sessionId}`);
      await axios.post(`${MCP_CLIENT_URL}/shutdown`, {
        session_id: bridgeSession.sessionId
      });
    } catch (error) {
      console.error(`[BRIDGE] Cleanup failed:`, error.message);
    }
  }
}

// Handle process termination
process.on('SIGINT', async () => {
  await cleanup();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await cleanup();
  process.exit(0);
});

/**
 * Start the bridge server
 */
async function main() {
  console.error(`[BRIDGE] Starting Insight Digger MCP Bridge`);
  console.error(`[BRIDGE] Connecting to MCP Client at: ${MCP_CLIENT_URL}`);
  console.error(`[BRIDGE] Logging enabled: ${ENABLE_LOGGING}, Debug level: ${DEBUG_LEVEL} (logs dir: ${LOGS_DIR})`);
  
  // Log bridge startup
  logToFile('bridge_start', { 
    mcpClientUrl: MCP_CLIENT_URL,
    loggingEnabled: ENABLE_LOGGING,
    debugLevel: DEBUG_LEVEL,
    version: '1.0.0'
  });
  
  const transport = new StdioServerTransport();
  await server.connect(transport);
  
  console.error(`[BRIDGE] Bridge ready. Waiting for authentication...`);
}

main().catch((error) => {
  console.error(`[BRIDGE] Fatal error:`, error);
  process.exit(1);
}); 