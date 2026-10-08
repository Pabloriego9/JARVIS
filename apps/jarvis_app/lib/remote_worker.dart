import 'dart:io';

import 'api.dart';

class RemoteWorker {
  final JarvisApi api;
  bool busy = false;
  RemoteWorker(this.api);
  Future<void> poll() async {
    if (!Platform.isAndroid ||
        busy ||
        await api.storage.read(key: 'receive_remote') != 'true') {
      return;
    }
    busy = true;
    try {
      final requests = await api.request('POST', '/v1/executor/poll') as List;
      for (final envelope in requests) {
        dynamic result;
        try {
          result = await LocalDevice.call('remote.execute', {
            'envelope': envelope,
          });
        } catch (e) {
          result = {
            'status': 'denied',
            'error_code': 'local_confirmation',
            'user_message': e.toString(),
            'retry_safe': false,
          };
        }
        // Keep evidence native-side; the mailbox never automatically dispatches this request again.
        await api.request(
          'POST',
          '/v1/executor/results/${envelope['request_id']}',
          result,
        );
      }
    } finally {
      busy = false;
    }
  }
}
