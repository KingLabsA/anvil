/**
 * Anvil Mobile App
 * A mobile coding assistant with voice, camera, and terminal access.
 */

import React, { useState, useEffect } from 'react';
import {
  SafeAreaView,
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Alert,
} from 'react-native';

const App = () => {
  const [task, setTask] = useState('');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    checkConnection();
  }, []);

  const checkConnection = async () => {
    try {
      const response = await fetch('http://localhost:8000/health');
      if (response.ok) {
        setConnected(true);
      }
    } catch (error) {
      setConnected(false);
    }
  };

  const runTask = async () => {
    if (!task.trim()) return;
    
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, model: 'local', max_iterations: 20 }),
      });
      
      const data = await response.json();
      setResult(data.success ? data.output : `Error: ${data.error}`);
    } catch (error) {
      setResult(`Connection error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const startVoiceInput = () => {
    // Voice input would use react-native-voice or similar
    Alert.alert('Voice Input', 'Voice input not yet implemented in demo');
  };

  const openCamera = () => {
    // Camera would use react-native-camera or similar
    Alert.alert('Camera', 'Camera capture not yet implemented in demo');
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>🔨 Anvil</Text>
        <Text style={styles.subtitle}>
          {connected ? '🟢 Connected' : '🔴 Disconnected'}
        </Text>
      </View>

      <ScrollView style={styles.content}>
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.input}
            value={task}
            onChangeText={setTask}
            placeholder="Describe a coding task..."
            multiline
          />
          <View style={styles.buttonRow}>
            <TouchableOpacity style={styles.voiceButton} onPress={startVoiceInput}>
              <Text style={styles.buttonText}>🎤 Voice</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.cameraButton} onPress={openCamera}>
              <Text style={styles.buttonText}>📷 Camera</Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity 
            style={[styles.runButton, loading && styles.disabled]} 
            onPress={runTask}
            disabled={loading}
          >
            <Text style={styles.buttonText}>
              {loading ? 'Running...' : '▶ Run Task'}
            </Text>
          </TouchableOpacity>
        </View>

        {result ? (
          <View style={styles.resultContainer}>
            <Text style={styles.resultLabel}>Result:</Text>
            <Text style={styles.resultText}>{result}</Text>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
  },
  header: {
    backgroundColor: '#111111',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#262626',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#f59e0b',
  },
  subtitle: {
    fontSize: 14,
    color: '#a0a0a0',
    marginTop: 4,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  inputContainer: {
    backgroundColor: '#111111',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  input: {
    backgroundColor: '#0a0a0a',
    borderWidth: 1,
    borderColor: '#262626',
    borderRadius: 8,
    padding: 12,
    color: '#ffffff',
    fontSize: 16,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 12,
  },
  voiceButton: {
    flex: 1,
    backgroundColor: '#238636',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  cameraButton: {
    flex: 1,
    backgroundColor: '#8957e5',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  runButton: {
    backgroundColor: '#238636',
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 12,
  },
  disabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  resultContainer: {
    backgroundColor: '#111111',
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
  },
  resultLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#f59e0b',
    marginBottom: 8,
  },
  resultText: {
    fontSize: 14,
    color: '#a0a0a0',
    lineHeight: 20,
  },
});

export default App;
