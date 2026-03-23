import 'dart:convert';
import 'dart:io';
import 'dart:async';
import 'package:http/http.dart' as http;

class GpuInfo {
  final bool hasNvidiaGpu;
  final String? gpuName;
  final bool driverInstalled;
  final String driverUrl;

  GpuInfo({
    required this.hasNvidiaGpu,
    this.gpuName,
    required this.driverInstalled,
    required this.driverUrl,
  });

  factory GpuInfo.fromJson(Map<String, dynamic> json) {
    return GpuInfo(
      hasNvidiaGpu: json['has_nvidia_gpu'] ?? false,
      gpuName: json['gpu_name'],
      driverInstalled: json['driver_installed'] ?? false,
      driverUrl: json['driver_url'] ?? 'https://www.nvidia.com/Download/index.aspx',
    );
  }
}

class HealthInfo {
  final String status;
  final String app;
  final String version;
  final String edgeTts;

  HealthInfo({
    required this.status,
    required this.app,
    required this.version,
    required this.edgeTts,
  });

  factory HealthInfo.fromJson(Map<String, dynamic> json) {
    return HealthInfo(
      status: json['status'] ?? 'unknown',
      app: json['app'] ?? 'unknown',
      version: json['version'] ?? 'unknown',
      edgeTts: json['edge_tts'] ?? 'unknown',
    );
  }
}

class BackendInfo {
  final String host;
  final int port;
  final String storageDir;
  final GpuInfo gpuInfo;

  BackendInfo({
    required this.host,
    required this.port,
    required this.storageDir,
    required this.gpuInfo,
  });

  factory BackendInfo.fromJson(Map<String, dynamic> json) {
    return BackendInfo(
      host: json['host'] ?? '127.0.0.1',
      port: json['port'] ?? 8000,
      storageDir: json['storage_dir'] ?? '',
      gpuInfo: GpuInfo.fromJson(json),
    );
  }

  String get baseUrl => 'http://$host:$port';
}

class BackendService {
  Process? _backendProcess;
  BackendInfo? _info;
  bool _isRunning = false;

  BackendInfo? get info => _info;
  bool get isRunning => _isRunning;
  String get baseUrl => _info?.baseUrl ?? 'http://127.0.0.1:8000';

  Future<BackendInfo?> startBackend(String backendExePath) async {
    if (_isRunning) return _info;

    final backendFile = File(backendExePath);
    if (!await backendFile.exists()) {
      throw Exception('Backend executable not found: $backendExePath');
    }

    _backendProcess = await Process.start(
      backendExePath,
      [],
      mode: ProcessStartMode.normal,
    );

    _backendProcess!.stdout.transform(utf8.decoder).listen((data) {
      print('[Backend] $data');
    });

    _backendProcess!.stderr.transform(utf8.decoder).listen((data) {
      print('[Backend Error] $data');
    });

    final tempDir = Platform.environment['TEMP'] ?? '/tmp';
    final infoFile = File('$tempDir/drama_remix_storage/backend_info.json');

    for (int i = 0; i < 60; i++) {
      await Future.delayed(const Duration(seconds: 1));
      if (await infoFile.exists()) {
        try {
          final content = await infoFile.readAsString();
          final json = jsonDecode(content);
          _info = BackendInfo.fromJson(json);
          _isRunning = true;
          return _info;
        } catch (e) {
          print('Failed to parse backend info: $e');
        }
      }
      if (_backendProcess!.pid != null) {
        final exitCode = await _backendProcess!.exitCode.timeout(
          Duration.zero,
          onTimeout: () => null,
        );
        if (exitCode != null) {
          throw Exception('Backend process exited with code: $exitCode');
        }
      }
    }

    throw Exception('Backend failed to start within 60 seconds');
  }

  Future<HealthInfo> checkHealth() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/health'));
      if (response.statusCode == 200) {
        return HealthInfo.fromJson(jsonDecode(response.body));
      }
      throw Exception('Health check failed: ${response.statusCode}');
    } catch (e) {
      throw Exception('Failed to connect to backend: $e');
    }
  }

  Future<GpuInfo> getGpuInfo() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/gpu-info'));
      if (response.statusCode == 200) {
        return GpuInfo.fromJson(jsonDecode(response.body));
      }
      throw Exception('GPU info request failed: ${response.statusCode}');
    } catch (e) {
      throw Exception('Failed to get GPU info: $e');
    }
  }

  Future<void> stopBackend() async {
    if (_backendProcess != null && _backendProcess!.pid != null) {
      _backendProcess!.kill();
      await _backendProcess!.exitCode;
      _backendProcess = null;
      _isRunning = false;
      _info = null;
    }
  }
}
