/// Коды значений контракта v0.2 (`contracts/`, `patient_state_v0.2.schema.json`).
///
/// Здесь только `wire`-значения, которыми клиент обменивается с backend.
/// Подписи для людей приходят с сервера (`GET /meta`), чтобы у приложения
/// и backend был один источник текстов.
library;

T _byWire<T extends Enum>(List<T> values, String wire, String Function(T) wireOf, String type) {
  for (final v in values) {
    if (wireOf(v) == wire) return v;
  }
  throw FormatException('Неизвестное значение $type: $wire');
}

enum DoctorPriority {
  info('info'),
  normal('normal'),
  high('high'),
  urgent('urgent');

  const DoctorPriority(this.wire);
  final String wire;

  /// Чем больше, тем выше в очереди врача.
  int get rank => index;

  static DoctorPriority fromWire(String w) => _byWire(values, w, (v) => v.wire, 'doctor_priority');

  static DoctorPriority max(Iterable<DoctorPriority> items) =>
      items.fold(DoctorPriority.info, (a, b) => b.rank > a.rank ? b : a);
}

enum PatientAction {
  none('none'),
  informAtNextContact('inform_at_next_contact'),
  neutralOutOfLeaflet('neutral_out_of_leaflet'),
  contactDoctorSoon('contact_doctor_soon'),
  contactClinicToday('contact_clinic_today'),
  recommendAmbulance('recommend_ambulance');

  const PatientAction(this.wire);
  final String wire;

  static PatientAction fromWire(String w) => _byWire(values, w, (v) => v.wire, 'patient_action');
}

enum Instrument {
  gad7('GAD7', 'GAD-7'),
  phq9('PHQ9', 'PHQ-9');

  const Instrument(this.wire, this.label);
  final String wire;
  final String label;

  static Instrument fromWire(String w) => _byWire(values, w, (v) => v.wire, 'instrument');
}

enum IntakeSlot {
  morning('morning'),
  evening('evening');

  const IntakeSlot(this.wire);
  final String wire;

  static IntakeSlot fromWire(String w) => _byWire(values, w, (v) => v.wire, 'slot');
}

enum IntakeStatus {
  taken('taken'),
  missed('missed'),
  unknown('unknown');

  const IntakeStatus(this.wire);
  final String wire;

  static IntakeStatus fromWire(String w) => _byWire(values, w, (v) => v.wire, 'status');
}

enum MissedReason {
  forgot('forgot'),
  adverseEvent('adverse_event'),
  feltUnwell('felt_unwell'),
  ranOut('ran_out'),
  decidedToStop('decided_to_stop'),
  other('other'),
  unknown('unknown');

  const MissedReason(this.wire);
  final String wire;

  static MissedReason fromWire(String w) => _byWire(values, w, (v) => v.wire, 'missed_reason');
}

enum SymptomType {
  somnolence('somnolence'),
  headache('headache'),
  dizziness('dizziness'),
  asthenia('asthenia'),
  paresthesia('paresthesia'),
  insomnia('insomnia'),
  poorSleepQuality('poor_sleep_quality'),
  anxietyIncreased('anxiety_increased'),
  attentionDisturbance('attention_disturbance'),
  slowedReaction('slowed_reaction'),
  dysgeusia('dysgeusia'),
  nausea('nausea'),
  upperAbdominalPain('upper_abdominal_pain'),
  constipation('constipation'),
  backPain('back_pain'),
  muscleRigidity('muscle_rigidity'),
  trismus('trismus'),
  hyperhidrosis('hyperhidrosis'),
  otherUnlisted('other_unlisted');

  const SymptomType(this.wire);
  final String wire;

  /// Входит ли тип в закрытый список нежелательных явлений из листка-вкладыша.
  bool get inLeafletSet => this != SymptomType.otherUnlisted;

  static SymptomType fromWire(String w) => _byWire(values, w, (v) => v.wire, 'normalized_type');
}

enum Tri {
  yes('yes'),
  no('no'),
  unknown('unknown');

  const Tri(this.wire);
  final String wire;

  static Tri fromWire(String w) => _byWire(values, w, (v) => v.wire, 'yes/no/unknown');
}

enum Severity {
  mild('mild'),
  moderate('moderate'),
  severe('severe'),
  unknown('unknown');

  const Severity(this.wire);
  final String wire;

  static Severity fromWire(String w) => _byWire(values, w, (v) => v.wire, 'severity');
}

enum RouteDecision {
  pending('pending'),
  none('none'),
  preferred('preferred'),
  required('required');

  const RouteDecision(this.wire);
  final String wire;

  static RouteDecision fromWire(String w) => _byWire(values, w, (v) => v.wire, 'doctor_decision');
}

enum AlertStatus {
  created('created'),
  deliveredToWorkplace('delivered_to_workplace'),
  viewed('viewed'),
  acknowledged('acknowledged'),
  resolved('resolved');

  const AlertStatus(this.wire);
  final String wire;

  bool get isOpen => this != AlertStatus.resolved;

  static AlertStatus fromWire(String w) => _byWire(values, w, (v) => v.wire, 'alert.status');
}

enum Role {
  patient('patient'),
  doctor('doctor'),
  admin('admin');

  const Role(this.wire);
  final String wire;

  static Role fromWire(String w) => _byWire(values, w, (v) => v.wire, 'role');
}
