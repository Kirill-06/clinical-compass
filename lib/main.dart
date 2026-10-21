import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app.dart';
import 'package:clinical_compass/app/app_services.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(ClinicalCompassApp(services: AppServices.http()));
}
