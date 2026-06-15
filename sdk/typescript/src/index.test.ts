/**
 * Tests for Anvil TypeScript SDK
 */

import { AnvilClient } from './index';
import axios from 'axios';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('AnvilClient', () => {
  let client: AnvilClient;

  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    // Create client with test config
    client = new AnvilClient({
      baseUrl: 'http://localhost:8765',
      timeout: 5000,
      model: 'local',
      maxIterations: 10
    });

    // Mock axios.create to return a mock instance
    const mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      defaults: {
        baseURL: '',
        timeout: 0
      }
    };
    mockedAxios.create.mockReturnValue(mockAxiosInstance as any);
  });

  describe('constructor', () => {
    it('should create client with default config', () => {
      const defaultClient = new AnvilClient();
      expect(defaultClient).toBeDefined();
      expect(mockedAxios.create).toHaveBeenCalledWith({
        baseURL: 'http://localhost:8765',
        timeout: 30000,
        headers: {
          'Content-Type': 'application/json'
        }
      });
    });

    it('should create client with custom config', () => {
      expect(client).toBeDefined();
      expect(mockedAxios.create).toHaveBeenCalledWith({
        baseURL: 'http://localhost:8765',
        timeout: 5000,
        headers: {
          'Content-Type': 'application/json'
        }
      });
    });
  });

  describe('run', () => {
    it('should execute task and return result', async () => {
      const mockResponse = {
        data: {
          success: true,
          output: 'Task completed',
          steps: 3,
          session_id: 'test-session-123'
        }
      };

      const mockPost = jest.fn().mockResolvedValue(mockResponse);
      (client as any).client.post = mockPost;

      const result = await client.run('Fix the bug');

      expect(mockPost).toHaveBeenCalledWith('/run', {
        task: 'Fix the bug',
        model: 'local',
        max_iterations: 10,
        verify: true
      });
      expect(result.success).toBe(true);
      expect(result.output).toBe('Task completed');
      expect(result.session_id).toBe('test-session-123');
    });

    it('should use custom options', async () => {
      const mockResponse = {
        data: {
          success: true,
          output: 'Done',
          steps: 1,
          session_id: 'test-456'
        }
      };

      const mockPost = jest.fn().mockResolvedValue(mockResponse);
      (client as any).client.post = mockPost;

      await client.run('Test task', {
        model: 'gpt-4',
        maxIterations: 5,
        verify: false
      });

      expect(mockPost).toHaveBeenCalledWith('/run', {
        task: 'Test task',
        model: 'gpt-4',
        max_iterations: 5,
        verify: false
      });
    });

    it('should handle server errors', async () => {
      const mockPost = jest.fn().mockRejectedValue({
        response: {
          status: 500,
          data: { detail: 'Internal error' }
        }
      });
      (client as any).client.post = mockPost;

      await expect(client.run('Bad task')).rejects.toThrow(
        'Anvil error (500): Internal error'
      );
    });

    it('should handle connection errors', async () => {
      const mockPost = jest.fn().mockRejectedValue({
        request: {}
      });
      (client as any).client.post = mockPost;

      await expect(client.run('Test')).rejects.toThrow(
        'Anvil server not reachable'
      );
    });
  });

  describe('getSession', () => {
    it('should retrieve session by ID', async () => {
      const mockSession = {
        id: 'session-123',
        task: 'Fix bug',
        steps: [],
        stats: {
          total_steps: 3,
          successful_steps: 3,
          failed_steps: 0,
          recovered_steps: 0,
          success_rate: 1.0,
          recovery_rate: 0
        },
        created_at: '2026-06-15T10:00:00Z',
        updated_at: '2026-06-15T10:05:00Z'
      };

      const mockGet = jest.fn().mockResolvedValue({ data: mockSession });
      (client as any).client.get = mockGet;

      const session = await client.getSession('session-123');

      expect(mockGet).toHaveBeenCalledWith('/sessions/session-123');
      expect(session.id).toBe('session-123');
      expect(session.task).toBe('Fix bug');
    });
  });

  describe('listSessions', () => {
    it('should list recent sessions', async () => {
      const mockSessions = [
        {
          id: 'session-1',
          task: 'Task 1',
          success: true,
          created_at: '2026-06-15T10:00:00Z'
        },
        {
          id: 'session-2',
          task: 'Task 2',
          success: false,
          created_at: '2026-06-15T09:00:00Z'
        }
      ];

      const mockGet = jest.fn().mockResolvedValue({ data: mockSessions });
      (client as any).client.get = mockGet;

      const sessions = await client.listSessions(10);

      expect(mockGet).toHaveBeenCalledWith('/sessions', { params: { limit: 10 } });
      expect(sessions).toHaveLength(2);
      expect(sessions[0].id).toBe('session-1');
    });
  });

  describe('health', () => {
    it('should check server health', async () => {
      const mockHealth = {
        status: 'ok',
        version: '0.3.0'
      };

      const mockGet = jest.fn().mockResolvedValue({ data: mockHealth });
      (client as any).client.get = mockGet;

      const health = await client.health();

      expect(mockGet).toHaveBeenCalledWith('/health');
      expect(health.status).toBe('ok');
      expect(health.version).toBe('0.3.0');
    });
  });

  describe('configure', () => {
    it('should update client configuration', () => {
      client.configure({
        baseUrl: 'http://new-server:9000',
        timeout: 10000,
        model: 'gpt-4'
      });

      expect((client as any).config.baseUrl).toBe('http://new-server:9000');
      expect((client as any).config.timeout).toBe(10000);
      expect((client as any).config.model).toBe('gpt-4');
    });
  });
});
