import time

from os.path import isfile
from PyQt5.QtCore import QObject, pyqtSlot

from arduino.programmerfactory import ProgrammerFactory
from instr.instrumentfactory import AnalyzerFactory, mock_enabled, SourceFactory, GeneratorFactory
from measureresult import MeasureResult


class InstrumentController(QObject):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.requiredInstruments = {
            'Анализатор': AnalyzerFactory('GPIB0::9::INSTR'),
            'Осциллограф': AnalyzerFactory('GPIB0::9::INSTR'),
            # 'Осциллограф': OscilloscopeFactory('GPIB0::9::INSTR'),
            'Источник 1': SourceFactory('GPIB0::1::INSTR'),
            'Источник 2': SourceFactory('GPIB0::2::INSTR'),
            'Генератор 1': GeneratorFactory('GPIB0::3::INSTR'),
            'Генератор 2': GeneratorFactory('GPIB0::4::INSTR'),
            'Программатор': ProgrammerFactory('COM5')
        }

        self.deviceParams = {
            'Цифровой делитель': {
                'F': [1.15, 1.35, 1.75, 1.92, 2.25, 2.54, 2.7, 3, 3.47, 3.86, 4.25],
                'mul': 2,
                'P1': 15,
                'P2': 21,
                'Istat': [None, None, None],
                'Idyn': [None, None, None]
            },
        }

        if isfile('./params.ini'):
            import ast
            with open('./params.ini', 'rt', encoding='utf-8') as f:
                raw = ''.join(f.readlines())
                self.deviceParams = ast.literal_eval(raw)

        self.secondaryParams = {
            'Pin': -20,
            'F1': 1.5,
            'F2': 4,
            'kp': 0,
            'Fborder1': 4,
            'Fborder2': 8
        }

        self.sweep_points = 201
        self.cal_set = 'CH1_CALREG'

        self._instruments = dict()
        self.found = False
        self.present = False
        self.hasResult = False

        self.result = MeasureResult()

        self._freqs = list()
        self._mag_s11s = list()
        self._mag_s22s = list()
        self._mag_s21s = list()
        self._phs_s21s = list()
        self._phase_codes = list()
        self._att_codes = list()

    def __str__(self):
        return f'{self._instruments}'

    def connect(self, addrs):
        print(f'searching for {addrs}')
        for k, v in addrs.items():
            self.requiredInstruments[k].addr = v
        self.found = self._find()

    def _find(self):
        self._instruments = {
            k: v.find() for k, v in self.requiredInstruments.items()
        }
        return all(self._instruments.values())

    def check(self, params):
        print(f'call check with {params}')
        device, secondary = params
        self.present = self._check(device, secondary)
        print('sample pass')

    def _check(self, device, secondary):
        print(f'launch check with {self.deviceParams[device]} {self.secondaryParams}')
        return self._runCheck(self.deviceParams[device], self.secondaryParams)

    def _runCheck(self, param, secondary):
        print(f'run check with {param}, {secondary}')
        return True

    def measure(self, params):
        print(f'call measure with {params}')
        device, secondary = params
        self.result.raw_data = \
            self.sweep_points, \
            self._measure(device, secondary), \
            self._phase_codes, \
            self._att_codes, \
            self.secondaryParams
        # self.hasResult = bool(self.result)
        self.hasResult = True

    def _measure(self, device, secondary):
        param = self.deviceParams[device]
        secondary = self.secondaryParams
        print(f'launch measure with {param} {secondary}')

        self._clear()
        self._init(secondary)

        return self._measure_s_params(secondary)

    def _clear(self):
        self._phase_codes.clear()
        self._att_codes.clear()

    def _init(self, params):
        pna = self._instruments['Анализатор']
        prog = self._instruments['Программатор']

        pna.send('SYST:PRES')
        pna.query('*OPC?')
        # pna.send('SENS1:CORR ON')

        pna.send('CALC1:PAR:DEF "CH1_S21",S21')

        # c:\program files\agilent\newtowrk analyzer\UserCalSets
        pna.send(f'SENS1:CORR:CSET:ACT "{self.cal_set}",1')

        pna.send(f'SENS1:SWE:POIN {self.sweep_points}')

        pna.send(f'SENS1:FREQ:STAR {params["F1"]}GHz')
        pna.send(f'SENS1:FREQ:STOP {params["F2"]}GHz')

        pna.send('SENS1:SWE:MODE CONT')
        pna.send(f'FORM:DATA ASCII')

        prog.set_lpf_code(0)

    def _measure_s_params(self, secondary):
        pna = self._instruments['Анализатор']
        prog = self._instruments['Программатор']

        out = []

        for _ in range(3):
            if not mock_enabled:
                time.sleep(0.5)

            pna.send(f'CALC1:PAR:SEL "CH1_S21"')
            pna.query('*OPC?')
            res = pna.query(f'CALC1:DATA:SNP? 2')

            # pna.send(f'CALC:DATA:SNP:PORTs:Save "1,2", "d:/ksa/psm_att/s_{att_code}_{psm_code}.s2p"')
            # pna.send(f'MMEM:STOR "d:/ksa/psm_att1/s_{att_code}_{psm_code}.s2p"')

            if mock_enabled:
                # with open(f'ref/sample_data/s_{att_code}_{psm_code}.s2p', mode='rt', encoding='utf-8') as f:
                #     res = list(f.readlines())[0].strip()
                print(_)
            out.append(parse_float_list(res))

            if not mock_enabled:
                time.sleep(0.5)
        return out

    @pyqtSlot(dict)
    def on_secondary_changed(self, params):
        self.secondaryParams = params

    @property
    def status(self):
        return [i.status for i in self._instruments.values()]


def parse_float_list(lst):
    return [float(x) for x in lst.split(',')]
