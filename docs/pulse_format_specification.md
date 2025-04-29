# Qudi Pulse Dateiformat-Spezifikation

Dieses Dokument beschreibt das Dateiformat, das von der Qudi-Software zum Speichern von Pulssequenzen verwendet wird. Die Pulse werden in einer hierarchischen Struktur organisiert und als JSON-Dateien gespeichert.

## 1. Hierarchie der Pulsobjekte

Die Pulsobjekte sind in einer vierstufigen Hierarchie organisiert:

### 1.1 PulseBlockElement

Die atomare Einheit einer Pulssequenz, die einen einzelnen Zeitabschnitt mit definierten Zuständen aller Kanäle repräsentiert.

**Eigenschaften:**
- `init_length_s`: Grunddauer des Elements in Sekunden
- `increment_s`: Inkrementierungswert für Parameter-Sweeps in Sekunden
- `laser_on`: Boolean, der angibt, ob der Laser während dieses Elements aktiv ist
- `digital_high`: Dictionary mit digitalen Kanälen als Schlüssel und Boolean-Werten
- `pulse_function`: Dictionary mit analogen Kanälen als Schlüssel und Funktionsbeschreibungen als Werte

### 1.2 PulseBlock

Eine Sammlung von PulseBlockElements, die eine logische Einheit bilden.

**Eigenschaften:**
- `name`: Eindeutiger Name des Pulsblocks
- `element_list`: Liste der enthaltenen PulseBlockElements
- Berechnete Eigenschaften:
  - `init_length_s`: Gesamtdauer des Blocks (Summe aller Elementdauern)
  - `increment_s`: Gesamtinkrementierung des Blocks (Summe aller Elementinkrementierungen)
  - `analog_channels`: Set aller verwendeten analogen Kanäle
  - `digital_channels`: Set aller verwendeten digitalen Kanäle

### 1.3 PulseBlockEnsemble

Eine Sammlung von PulseBlocks mit Wiederholungszahlen, die eine vollständige Messsequenz definiert.

**Eigenschaften:**
- `name`: Eindeutiger Name des Ensembles
- `block_list`: Liste von Tupeln (PulseBlock-Name, Wiederholungen)
- `rotating_frame`: Boolean, der angibt, ob die Phase über alle Waveforms hinweg erhalten bleibt
- `sampling_information`: Dictionary mit Informationen zum Sampling-Prozess
- `measurement_information`: Dictionary mit Informationen zur Messung
- `generation_method_parameters`: Dictionary mit Parametern für die Erzeugungsmethode

### 1.4 PulseSequence

Eine höherwertige Anordnung von PulseBlockEnsembles für komplexe Abläufe.

**Eigenschaften:**
- `name`: Eindeutiger Name der Sequenz
- `ensemble_list`: Liste von SequenceStep-Objekten
- `rotating_frame`: Boolean, der angibt, ob die Phase über alle Waveforms hinweg erhalten bleibt
- `sampling_information`: Dictionary mit Informationen zum Sampling-Prozess
- `measurement_information`: Dictionary mit Informationen zur Messung

## 2. JSON-Dateiformat

Alle Pulsobjekte werden als JSON-Dateien gespeichert. Im Folgenden sind die genauen Formate mit Beispielen beschrieben.

### 2.1 PulseBlockElement-Repräsentation

PulseBlockElement-Objekte erscheinen als Teil von PulseBlock-Dateien und haben folgendes Format:

```json
{
  "init_length_s": 1e-08,
  "increment_s": 0,
  "laser_on": false,
  "digital_high": {
    "d_ch1": true,
    "d_ch2": false
  },
  "pulse_function": {
    "a_ch1": {
      "name": "Sin",
      "params": {
        "amplitude": 0.5,
        "frequency": 2.87e+09,
        "phase": 0
      }
    }
  }
}
```

#### Sampling-Funktionen für analoge Kanäle

Die folgenden Funktionen sind für analoge Kanäle verfügbar:

1. **DC**
   ```json
   {
     "name": "DC",
     "params": {
       "voltage": 1.0
     }
   }
   ```

2. **Sin** (Sinus)
   ```json
   {
     "name": "Sin",
     "params": {
       "amplitude": 0.5,
       "frequency": 2.87e+09,
       "phase": 0
     }
   }
   ```

3. **DoubleSinSum** (Summe zweier Sinusfunktionen)
   ```json
   {
     "name": "DoubleSinSum",
     "params": {
       "amplitude_1": 0.5,
       "frequency_1": 2.87e+09,
       "phase_1": 0,
       "amplitude_2": 0.3,
       "frequency_2": 2.88e+09,
       "phase_2": 90
     }
   }
   ```

4. **Chirp** (Linear frequenzmodulierter Puls)
   ```json
   {
     "name": "Chirp",
     "params": {
       "amplitude": 0.5,
       "start_freq": 2.87e+09,
       "stop_freq": 2.88e+09,
       "phase": 0
     }
   }
   ```

5. **Idle** (Keine Ausgabe, 0V)
   ```json
   {
     "name": "Idle",
     "params": {}
   }
   ```

### 2.2 PulseBlock-Datei

```json
{
  "name": "rabi_block",
  "element_list": [
    {
      "init_length_s": 1e-08,
      "increment_s": 0,
      "laser_on": false,
      "digital_high": {"d_ch1": false},
      "pulse_function": {"a_ch1": {"name": "Idle", "params": {}}}
    },
    {
      "init_length_s": 2e-08,
      "increment_s": 1e-09,
      "laser_on": false,
      "digital_high": {"d_ch1": true},
      "pulse_function": {"a_ch1": {"name": "Sin", "params": {"amplitude": 0.5, "frequency": 2.87e+09, "phase": 0}}}
    },
    {
      "init_length_s": 3e-07,
      "increment_s": 0,
      "laser_on": true,
      "digital_high": {"d_ch1": false},
      "pulse_function": {"a_ch1": {"name": "Idle", "params": {}}}
    }
  ]
}
```

### 2.3 PulseBlockEnsemble-Datei

```json
{
  "name": "rabi_ensemble",
  "rotating_frame": true,
  "block_list": [
    ["initialization_block", 0],
    ["rabi_block", 20],
    ["readout_block", 0]
  ],
  "sampling_information": {
    "sample_rate": 1.25e+09,
    "activation_config": ["analog_digital", {"a_ch1": ["laser"], "d_ch1": ["mw"]}],
    "analog_channels": {"a_ch1": ["laser"]},
    "digital_channels": {"d_ch1": ["mw"]},
    "waveforms": ["waveform_1", "waveform_2"],
    "sequence_name": "sequence_rabi"
  },
  "measurement_information": {
    "alternating": false,
    "laser_ignore_list": [],
    "controlled_variable": [0, 1e-09, 2e-09, 3e-09, 4e-09, 5e-09, 6e-09, 7e-09, 8e-09, 9e-09, 1e-08, 1.1e-08, 1.2e-08, 1.3e-08, 1.4e-08, 1.5e-08, 1.6e-08, 1.7e-08, 1.8e-08, 1.9e-08, 2e-08],
    "units": ["s", ""],
    "labels": ["Pulslänge", "Signal"],
    "number_of_lasers": 20,
    "counting_length": 3e-07
  },
  "generation_method_parameters": {
    "method": "rabi",
    "rabi_period": 2e-08,
    "laser_length": 3e-07,
    "laser_delay": 1e-08,
    "microwave_channel": "d_ch1",
    "laser_channel": "d_ch2",
    "sync_channel": ""
  }
}
```

### 2.4 PulseSequence-Datei

```json
{
  "name": "my_sequence",
  "rotating_frame": true,
  "ensemble_list": [
    {
      "ensemble": "ensemble_name1",
      "repetitions": 10,
      "go_to": -1,
      "event_jump_to": -1,
      "event_trigger": "OFF",
      "wait_for": "OFF",
      "flag_trigger": [],
      "flag_high": []
    },
    {
      "ensemble": "ensemble_name2",
      "repetitions": 5,
      "go_to": 0,
      "event_jump_to": -1,
      "event_trigger": "OFF",
      "wait_for": "OFF",
      "flag_trigger": [],
      "flag_high": []
    }
  ],
  "sampling_information": {
    "waveforms": ["waveform_1", "waveform_2", "waveform_3", "waveform_4"],
    "sequence_name": "sequence_complex"
  },
  "measurement_information": {
    "alternating": true,
    "laser_ignore_list": [0, 1],
    "controlled_variable": [0, 1e-08, 2e-08, 3e-08, 4e-08, 5e-08],
    "units": ["s", ""],
    "labels": ["Zeit", "Signal"],
    "number_of_lasers": 120,
    "counting_length": 3e-07
  }
}
```

## 3. Sequenzparameter

### 3.1 SequenceStep-Parameter

Ein SequenceStep definiert, wie ein bestimmtes Ensemble in einer Sequenz abgespielt wird:

- `ensemble`: Name des zu spielenden Ensembles (String)
- `repetitions`: Anzahl der Wiederholungen (Integer)
  - 0: Einmal abspielen
  - n > 0: n+1 mal abspielen
  - -1: Unendliche Wiederholung
- `go_to`: Index des nächsten zu spielenden Schritts (Integer)
  - -1 oder 0: Nächster Schritt
  - n > 0: Springe zu Schritt n (1-basierter Index)
- `event_jump_to`: Zielschritt im Falle eines Triggerereignisses (Integer)
- `event_trigger`: Trigger-Eingang für Sprünge (String)
- `wait_for`: Trigger-Eingang, auf den gewartet werden soll (String)
- `flag_trigger`: Liste von Flags, die beim Start dieses Schritts ausgelöst werden sollen (List)
- `flag_high`: Liste von Flags, die während dieses Schritts high sein sollen (List)

### 3.2 Measurement Information

Das Dictionary `measurement_information` enthält Informationen für die Messauswertung:

- `alternating`: Boolean, der angibt, ob alternierende Messungen durchgeführt werden
- `laser_ignore_list`: Liste von Laserindizes, die bei der Analyse ignoriert werden sollen
- `controlled_variable`: Liste der Werte der unabhängigen Variable (z.B. Zeitwerte)
- `units`: Liste mit Einheiten für x- und y-Achse
- `labels`: Liste mit Beschriftungen für x- und y-Achse
- `number_of_lasers`: Gesamtzahl der Laserpulse in der Messung
- `counting_length`: Dauer der Zählung für jeden Datenpunkt

### 3.3 Sampling Information

Das Dictionary `sampling_information` enthält Informationen zum Sampling-Prozess:

- `sample_rate`: Abtastrate in Hz
- `activation_config`: Konfiguration der aktiven Kanäle
- `analog_channels`: Dictionary der analogen Kanäle und ihrer Funktionen
- `digital_channels`: Dictionary der digitalen Kanäle und ihrer Funktionen
- `waveforms`: Liste der erzeugten Waveform-Namen
- `sequence_name`: Name der erzeugten Sequenzdatei

## 4. Speicherort und Laden/Speichern

### 4.1 Standard-Speicherorte

Die Puls-Dateien werden standardmäßig in folgenden Verzeichnissen gespeichert:

- PulseBlocks: `<user_dir>/saved_blocks/`
- PulseBlockEnsembles: `<user_dir>/saved_ensembles/`
- PulseSequences: `<user_dir>/saved_sequences/`

### 4.2 Speichern

Das Speichern erfolgt durch:

1. Die GUI:
   - "Save"-Button im entsprechenden Tab klicken
   - Namen eingeben und Speichern bestätigen

2. Die Logik-Methoden:
   - `save_block(block_name)`: Speichert einen PulseBlock
   - `save_ensemble(ensemble_name)`: Speichert ein PulseBlockEnsemble
   - `save_sequence(sequence_name)`: Speichert eine PulseSequence

### 4.3 Laden

Das Laden erfolgt durch:

1. Die GUI:
   - "Load"-Button im entsprechenden Tab klicken
   - Datei aus Liste auswählen

2. Die Logik-Methoden:
   - `load_block(block_name)`: Lädt einen PulseBlock
   - `load_ensemble(ensemble_name)`: Lädt ein PulseBlockEnsemble und alle abhängigen Blocks
   - `load_sequence(sequence_name)`: Lädt eine PulseSequence und alle abhängigen Ensembles und Blocks

## 5. Praktische Beispiele

### 5.1 Rabi-Oszillation

Eine typische Rabi-Messung besteht aus:

1. Einem Initialisierungsblock (Laser-Puls zur Spin-Initialisierung)
2. Einem MW-Puls mit variabler Länge (Sweep-Parameter)
3. Einem Ausleseblock (Laser-Puls und Fluoreszenzdetektion)

```json
// Rabi-Ensemble-Beispiel
{
  "name": "rabi_ensemble",
  "rotating_frame": true,
  "block_list": [
    ["init_block", 0],
    ["mw_block", 0],
    ["readout_block", 0]
  ],
  "measurement_information": {
    "controlled_variable": [10e-9, 20e-9, 30e-9, ... 500e-9],
    "units": ["s", "counts"],
    "labels": ["MW Pulslänge", "Fluoreszenz"]
  }
}
```

### 5.2 Ramsey-Interferometrie

Eine typische Ramsey-Messung besteht aus:

1. Initialisierungsblock
2. π/2-Puls
3. Variabler Wartezeit
4. Zweitem π/2-Puls
5. Ausleseblock

```json
// Ramsey-Ensemble-Beispiel
{
  "name": "ramsey_ensemble",
  "rotating_frame": true,
  "block_list": [
    ["init_block", 0],
    ["pi_half_block", 0],
    ["wait_block", 0],
    ["pi_half_block", 0],
    ["readout_block", 0]
  ],
  "measurement_information": {
    "controlled_variable": [100e-9, 200e-9, 300e-9, ... 5000e-9],
    "units": ["s", "counts"],
    "labels": ["Wartezeit", "Fluoreszenz"]
  }
}
```