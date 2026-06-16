/**
 * Tests for Anvil Mobile App
 */

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import App from '../App';

// Mock fetch
global.fetch = jest.fn();

describe('App', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'ok' }),
    });
  });

  it('renders correctly', () => {
    const { getByText } = render(<App />);
    expect(getByText('🔨 Anvil')).toBeTruthy();
  });

  it('shows connection status', async () => {
    const { getByText } = render(<App />);
    await waitFor(() => {
      expect(getByText('🟢 Connected')).toBeTruthy();
    });
  });

  it('disables run button when loading', async () => {
    const { getByText, getByPlaceholderText } = render(<App />);
    (global.fetch as jest.Mock).mockImplementation(() => 
      new Promise(resolve => setTimeout(() => resolve({
        ok: true,
        json: () => Promise.resolve({ success: true, output: 'Done' }),
      }), 100))
    );
    fireEvent.changeText(getByPlaceholderText('Describe a coding task...'), 'Test task');
    fireEvent.press(getByText('▶ Run Task'));
    expect(getByText('Running...')).toBeTruthy();
  });

  it('displays result after task completion', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, output: 'Task completed' }),
    });
    const { getByText, getByPlaceholderText } = render(<App />);
    fireEvent.changeText(getByPlaceholderText('Describe a coding task...'), 'Test task');
    fireEvent.press(getByText('▶ Run Task'));
    await waitFor(() => {
      expect(getByText('Task completed')).toBeTruthy();
    });
  });
});
