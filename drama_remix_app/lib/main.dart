import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/backend_service.dart';

void main() {
  runApp(const DramaRemixApp());
}

class DramaRemixApp extends StatelessWidget {
  const DramaRemixApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AppState(),
      child: MaterialApp(
        title: 'Drama Remix Tool',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
          useMaterial3: true,
        ),
        home: const HomePage(),
      ),
    );
  }
}

class AppState extends ChangeNotifier {
  final BackendService _backendService = BackendService();
  BackendInfo? _backendInfo;
  HealthInfo? _healthInfo;
  bool _isLoading = false;
  String? _error;
  String? _statusMessage;

  BackendInfo? get backendInfo => _backendInfo;
  HealthInfo? get healthInfo => _healthInfo;
  bool get isLoading => _isLoading;
  String? get error => _error;
  String? get statusMessage => _statusMessage;
  String get baseUrl => _backendService.baseUrl;

  Future<void> startBackend() async {
    _isLoading = true;
    _error = null;
    _statusMessage = 'Starting backend...';
    notifyListeners();

    try {
      final exePath = _findBackendExe();
      _backendInfo = await _backendService.startBackend(exePath);
      _statusMessage = 'Backend started. Checking health...';
      notifyListeners();

      _healthInfo = await _backendService.checkHealth();
      _statusMessage = 'Backend is ready!';
      _error = null;
    } catch (e) {
      _error = e.toString();
      _statusMessage = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  String _findBackendExe() {
    final exeDir = File(Platform.resolvedExecutable).parent.path;
    final backendExe = File('$exeDir/backend/backend.exe');
    if (backendExe.existsSync()) {
      return backendExe.path;
    }

    final altPath = File('$exeDir/../backend/backend.exe');
    if (altPath.existsSync()) {
      return altPath.path;
    }

    throw Exception(
      'Backend executable not found. Please place backend.exe in the app directory.'
    );
  }

  Future<void> checkHealth() async {
    if (!_backendService.isRunning) return;
    try {
      _healthInfo = await _backendService.checkHealth();
      _error = null;
    } catch (e) {
      _error = e.toString();
    }
    notifyListeners();
  }

  Future<void> stopBackend() async {
    await _backendService.stopBackend();
    _backendInfo = null;
    _healthInfo = null;
    _statusMessage = null;
    notifyListeners();
  }

  @override
  void dispose() {
    stopBackend();
    super.dispose();
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AppState>().startBackend();
    });
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Drama Remix Tool'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          if (appState.healthInfo != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Chip(
                avatar: const Icon(Icons.check_circle, color: Colors.green, size: 18),
                label: Text('Online (${appState.healthInfo!.version})'),
              ),
            ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: appState.checkHealth,
            tooltip: 'Check backend health',
          ),
        ],
      ),
      body: appState.isLoading
          ? const Center(child: CircularProgressIndicator())
          : appState.error != null
              ? _buildErrorView(appState)
              : _buildMainContent(appState),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (i) => setState(() => _selectedIndex = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.folder), label: 'Materials'),
          NavigationDestination(icon: Icon(Icons.play_arrow), label: 'Tasks'),
          NavigationDestination(icon: Icon(Icons.video_library), label: 'Gallery'),
        ],
      ),
    );
  }

  Widget _buildErrorView(AppState appState) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 64, color: Colors.red),
          const SizedBox(height: 16),
          Text(
            'Failed to start backend',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              appState.error!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.red),
            ),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: appState.startBackend,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  Widget _buildMainContent(AppState appState) {
    if (_selectedIndex == 0) {
      return _buildHomeContent(appState);
    }
    return _buildPlaceholder();
  }

  Widget _buildHomeContent(AppState appState) {
    final gpuInfo = appState.backendInfo?.gpuInfo;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            child: ListTile(
              leading: Icon(
                gpuInfo?.hasNvidiaGpu == true
                    ? Icons.memory
                    : Icons.memory_outlined,
                color: gpuInfo?.hasNvidiaGpu == true ? Colors.green : Colors.grey,
                size: 32,
              ),
              title: Text(
                gpuInfo?.hasNvidiaGpu == true
                    ? (gpuInfo?.gpuName ?? 'NVIDIA GPU')
                    : 'No NVIDIA GPU (CPU mode)',
              ),
              subtitle: gpuInfo?.hasNvidiaGpu == true
                  ? Text(
                      gpuInfo!.driverInstalled
                          ? 'Driver: Installed'
                          : 'Driver: NOT INSTALLED - ${gpuInfo.driverUrl}',
                      style: TextStyle(
                        color: gpuInfo.driverInstalled ? Colors.green : Colors.red,
                      ),
                    )
                  : null,
            ),
          ),
          const SizedBox(height: 16),
          if (appState.healthInfo != null) ...[
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.cloud_done),
                    title: const Text('Backend Status'),
                    subtitle: Text(
                      '${appState.healthInfo!.app} v${appState.healthInfo!.version}',
                    ),
                  ),
                  ListTile(
                    leading: const Icon(Icons.record_voice_over),
                    title: const Text('Edge TTS'),
                    subtitle: Text(appState.healthInfo!.edgeTts),
                  ),
                  ListTile(
                    leading: const Icon(Icons.link),
                    title: const Text('API Base URL'),
                    subtitle: Text(appState.baseUrl),
                  ),
                ],
              ),
            ),
          ],
          if (appState.statusMessage != null) ...[
            const SizedBox(height: 16),
            Card(
              color: Colors.blue.shade50,
              child: ListTile(
                leading: const Icon(Icons.info),
                title: Text(appState.statusMessage!),
              ),
            ),
          ],
          const SizedBox(height: 24),
          Text(
            'Quick Actions',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              ActionChip(
                avatar: const Icon(Icons.folder_open),
                label: const Text('Import Materials'),
                onPressed: () {},
              ),
              ActionChip(
                avatar: const Icon(Icons.video_library),
                label: const Text('View Gallery'),
                onPressed: () => setState(() => _selectedIndex = 3),
              ),
              ActionChip(
                avatar: const Icon(Icons.play_arrow),
                label: const Text('Create Task'),
                onPressed: () => setState(() => _selectedIndex = 2),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPlaceholder() {
    return Center(
      child: Text(
        'This feature is under development.\nConnect to the web interface at http://localhost:5173',
        textAlign: TextAlign.center,
        style: Theme.of(context).textTheme.titleMedium,
      ),
    );
  }
}
