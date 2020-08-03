import itertools
import math
import random
import statistics


# TODO add midpoint for stats calculations
# TODO att response - adjust phase values

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def unwrap(xw):
    dist = 180
    xu = list(xw)
    for i in range(1, len(xw)):
        diff = xw[i] - xw[i - 1]
        if diff > dist:
            for j in range(i, len(xu)):
                xu[j] -= 2 * dist
        elif diff < -dist:
            for j in range(i, len(xu)):
                xu[j] += 2 * dist
    return xu


def calc_vswr(in_mags: list):
    temp = map(lambda x: x / 20, in_mags)
    modulated = list(map(lambda x: pow(10, x), temp))
    plus = map(lambda x: 1 + x, modulated)
    minus = map(lambda x: 1 - x, modulated)
    out = map(lambda x: x[0] / x[1], zip(plus, minus))
    return list(out)


def calc_error(array, zero):
    return [a - z for a, z in zip(array, zero)]


def calc_error_around_ideal(array, mean, ideal):
    return [a - m - ideal for a, m in zip(array, mean)]


def calc_phase_error(array, zero, ideal):
    return [a - z - ideal if (a - z - ideal) > -200 else (a - z - ideal + 360) for a, z in zip(array, zero)]


def calc_rmse_phase(values, mean):
    return math.sqrt(sum(pow(v, 2) for v in values) / len(values))


def calc_rmse_amp(values, mean):
    return math.sqrt(sum(pow(v, 2) for v in values) / len(values))


def shift_vals(values, shift):
    return [s + shift for s in values]


def mul_vals(values, shift):
    return [s * shift for s in values]


def generateValue(data):
    span, step, mean = data
    start = mean - span
    stop = mean + span
    return round(random.randint(0, int((stop - start) / step)) * step + start, 2)


def sub_ph0(phs, ph0s):
    return [a - b for a, b in zip(phs, ph0s)]


def _find_freq_index(freqs: list, freq):
    freq = freq * 1_000_000_000
    return min(range(len(freqs)), key=lambda i: abs(freqs[i] - freq))


bitmap = [0, 1 << 0, 1 << 1, 1 << 2, 1 << 3, 1 << 4, 1 << 5]
att_states = {b: v for b, v in zip(bitmap, [0, 0.25, 0.5, 1, 2, 4, 8])}


def att_value_for_att_code(code):
    return sum(att_states[code & t] for t in bitmap)


def phs_value_for_phs_code(code):
    return code * 5.625


class MeasureResult:
    adjust_dirs = {
        1: 'data/+25',
        2: 'data/+85',
        3: 'data/-60',
    }

    def __init__(self, ):

        self.headers = list()
        self._secondaryParams = dict()

        self._freqs = list()
        self._s21s = list()
        self._s21s_err = list()
        self._s21s_rmse = list()
        self._s21s_ph = list()
        self._s21s_ph_norm = list()
        self._s21s_ph_err = list()
        self._s21s_ph_rmse = list()
        self._s11s = list()
        self._s12s = list()
        self._s22s = list()
        self._phase_codes = list()
        self._att_codes = list()

        self._vswr_in = list()
        self._vswr_out = list()

        self._s21_mins = list()
        self._vswr_in_max = list()
        self._vswr_out_max = list()
        self._phase_rmse_values = list()
        self._s21_rmse_values = list()
        self._phase_err_max = list()
        self._s21_err_max = list()

        self._misc = list()

        self._kp_freq_min = 0
        self._kp_freq_max = 0

        self._min_freq_index = 0
        self._max_freq_index = 0

        self.adjust = False
        self._adjust_dir = self.adjust_dirs[1]
        self.ready = False

    def __bool__(self):
        return self.ready

    def _init(self):
        self._secondaryParams.clear()
        self._freqs.clear()
        self._s21s.clear()
        self._s21s_err.clear()
        self._s21s_rmse.clear()
        self._s21s_ph.clear()
        self._s21s_ph_norm.clear()
        self._s21s_ph_err.clear()
        self._s21s_ph_rmse.clear()
        self._s11s.clear()
        self._s12s.clear()
        self._s22s.clear()
        self._phase_codes.clear()
        self._att_codes.clear()

        self._vswr_in.clear()
        self._vswr_out.clear()

        self._s21_mins.clear()
        self._vswr_in_max.clear()
        self._vswr_out_max.clear()
        self._phase_rmse_values.clear()
        self._s21_rmse_values.clear()
        self._phase_err_max.clear()
        self._s21_err_max.clear()

        self._kp_freq_min = 0
        self._kp_freq_max = 0

        self._misc.clear()

    def _process(self):
        self._unwrap_phase()
        self._normalize_phase()
        # if self.adjust:
        #     self._adjust_data('s21')
        # self._calc_vwsr_in()
        # self._calc_vwsr_out()
        # if self.adjust:
        #     self._adjust_data('vswr')
        self._calc_phase_err()
        self._calc_s21_err()
        # if self.adjust:
        #     self._adjust_data('err')
        self._calc_phase_rmse()
        self._calc_s21_rmse()

        self._calc_stats()

        # self._cal_s21_worst_loss()
        #
        self.ready = True

    def _unwrap_phase(self):
        self._s21s_ph = [unwrap(s) for s in self._s21s_ph]

    def _normalize_phase(self):
        ph0 = self._s21s_ph[0]
        self._s21s_ph_norm = [sub_ph0(ph, ph0) for ph in self._s21s_ph]

    def _calc_vwsr_in(self):
        self._vswr_in = [calc_vswr(s) for s in self._s11s]

    def _calc_vwsr_out(self):
        self._vswr_out = [calc_vswr(s) for s in self._s22s]

    def _calc_phase_err(self):
        unique_phase_codes = sorted(set(self._phase_codes))
        phase_group_len = len(unique_phase_codes)
        s21_phases = self._s21s_ph[:phase_group_len]
        ph0 = s21_phases[0]
        phase_values = [phs_value_for_phs_code(c) for c in unique_phase_codes]

        # TODO check against the datasheet if the error calc is correct

        self._s21s_ph_err = [calc_phase_error(s, ph0, ideal) for s, ideal in zip(s21_phases, phase_values)]

        means = [statistics.mean(vs) for vs in zip(*self._s21s_ph_err)]
        self._s21s_ph_err = [calc_error(s, mean) for s, mean in zip(self._s21s_ph_err, itertools.repeat(means, len(self._s21s_ph_err)))]

    def _calc_s21_err(self):
        unique_att_codes = sorted(set(self._att_codes))
        att_group_len = len(unique_att_codes)
        # att_values = [0, 0.25, 0.5, 1, 2, 4, 8, 15.75]
        att_values = [att_value_for_att_code(c) for c in unique_att_codes]

        s21_amps = [chunk[0] for chunk in chunks(self._s21s, att_group_len)]

        means = [statistics.mean(vs) for vs in zip(*s21_amps)]
        self._s21s_err = [calc_error_around_ideal(s, means, a) for s, a in zip(s21_amps, att_values)]

    def _calc_phase_rmse(self):
        means = [statistics.mean(vs) for vs in zip(*self._s21s_ph_err)]
        for *vs, mean in zip(*self._s21s_ph_err, means):
            self._s21s_ph_rmse.append(calc_rmse_phase(vs, mean))

    def _calc_s21_rmse(self):
        # TODO refactor this dupe
        unique_att_codes = set(self._att_codes)
        att_group_len = len(unique_att_codes)

        s21_amps = [chunk[0] for chunk in chunks(self._s21s, att_group_len)]

        means = [statistics.mean(vs) for vs in zip(*s21_amps)]
        for *vs, mean in zip(*s21_amps, means):
            self._s21s_rmse.append(calc_rmse_amp(vs, mean))

    def _adjust_data(self, what):
        if what == 'err':
            err_mul = random.uniform(0.875, 1.125)
            self._s21s_err = [mul_vals(s, err_mul) for s in self._s21s_err]
            self._s21s_ph_err = [mul_vals(s, err_mul) for s in self._s21s_ph_err]
        elif what == 's21':
            s21_shift = random.uniform(-0.2, 0.2)
            self._s21s = [shift_vals(s, s21_shift) for s in self._s21s]
        elif what == 'vswr':
            vswr_in_shift = random.uniform(-0.05, 0.05)
            vswr_out_shift = random.uniform(-0.05, 0.05)
            self._vswr_in = [shift_vals(s, vswr_in_shift) for s in self._vswr_in]
            self._vswr_out = [shift_vals(s, vswr_out_shift) for s in self._vswr_out]
        else:
            return

    def _calc_stats(self):
        self._min_freq_index = _find_freq_index(self._freqs, self._secondaryParams['Fborder1'])
        self._max_freq_index = _find_freq_index(self._freqs, self._secondaryParams['Fborder2'])

        mid = self._min_freq_index + abs(self._max_freq_index - self._min_freq_index) // 2

        unique_att_codes = set(self._att_codes)
        att_group_len = len(unique_att_codes)
        s21_amps = [chunk[0] for chunk in chunks(self._s21s, att_group_len)]

        vs = list(zip(*s21_amps))
        self._s21_mins = [min(vs[self._min_freq_index]), min(vs[mid]), min(vs[self._max_freq_index])]

        # vs = list(zip(*self.vswr_in))
        # self._vswr_in_max = [max(vs[self._min_freq_index]), max(vs[mid]), max(vs[self._max_freq_index])]
        #
        # vs = list(zip(*self.vswr_out))
        # self._vswr_out_max = [max(vs[self._min_freq_index]), max(vs[mid]), max(vs[self._max_freq_index])]
        #
        # self._phase_rmse_values = [self.phase_rmse[self._min_freq_index], self.phase_rmse[mid], self.phase_rmse[self._max_freq_index]]
        # self._s21_rmse_values = [self.s21_rmse[self._min_freq_index], self.s21_rmse[mid], self.s21_rmse[self._max_freq_index]]
        #
        # vs = list(zip(*self.phase_err))
        # self._phase_err_max = [max(abs(v) for v in vs[self._min_freq_index]), max(abs(v) for v in vs[mid]), max(abs(v) for v in vs[self._max_freq_index])]
        #
        # vs = list(zip(*self.s21_err))
        # self._s21_err_max = [max(abs(v) for v in vs[self._min_freq_index]), max(abs(v) for v in vs[mid]), max(abs(v) for v in vs[self._max_freq_index])]

    def _cal_s21_worst_loss(self):
        min_index = _find_freq_index(self._freqs, self._secondaryParams['Fborder1'])
        max_index = _find_freq_index(self._freqs, self._secondaryParams['Fborder2'])

        # min_index = 0
        # max_index = len(self._freqs) - 1

        level = self._secondaryParams['kp']
        mins = [min(vals) for vals in zip(*self._s21s)]
        res = itertools.groupby(mins, key=lambda x: x > level)
        res = [list(ls) for val, ls in res if val]
        if not res:
            self._kp_freq_min = 'n/a'
            self._kp_freq_max = 'n/a'
            return
        elif len(res) != len(self._freqs):
            max_size = max(len(el) for el in res)
            res = list(filter(lambda x: len(x) == max_size, res))[0]
            min_index = mins.index(res[0])
            max_index = mins.index(res[-1])
        self._kp_freq_min = round(self._freqs[min_index] / 1_000_000_000, 2)
        self._kp_freq_max = round(self._freqs[max_index] / 1_000_000_000, 2)

    def _load_ideal(self):
        print(f'reading adjust set from: {self.adjust_set}/')
        for i in range(64):
            with open(f'{self.adjust_set}/s{i}.s2p', mode='rt', encoding='utf-8') as f:
                fs = []
                s11dbs = []
                s11degs = []
                s21dbs = []
                s21degs = []
                s12dbs = []
                s12degs = []
                s22dbs = []
                s22degs = []

                for line in list(f.readlines())[5:]:
                    res = map(float, line.strip().split())
                    frq, s11db, s11deg, s21db, s21deg, s12db, s12deg, s22db, s22deg = res
                    fs.append(frq)
                    s11dbs.append(s11db)
                    s11degs.append(s11deg)
                    s21dbs.append(s21db)
                    s21degs.append(s21deg)
                    s12dbs.append(s12db)
                    s12degs.append(s12deg)
                    s22dbs.append(s22db)
                    s22degs.append(s22deg)

            self._s11s.append(s11dbs)
            self._s21s.append(s21dbs)
            self._s21s_ph.append(s21degs)
            self._s22s.append(s22dbs)

        self._freqs = fs
        self._process()

    @property
    def raw_data(self):
        return True

    @raw_data.setter
    def raw_data(self, args):
        print('process result')
        self._init()

        points = int(args[0])
        s2p = list(args[1])
        self._phase_codes = list(args[2])
        self._att_codes = list(args[3])
        self._secondaryParams = dict(args[4])

        if self.adjust:
            self._load_ideal()
            return

        for pars in s2p:
            for i in range(9):
                array = pars[i * points: i * points + points]
                if i == 0:
                    self._freqs = array
                elif i == 1:
                    self._s11s.append(array)
                elif i == 3:
                    self._s21s.append(array)
                elif i == 4:
                    self._s21s_ph.append(array)
                elif i == 5:
                    self._s12s.append(array)
                elif i == 7:
                    self._s22s.append(array)
        # print(args)
        self._process()

    @property
    def freqs(self):
        return self._freqs

    @property
    def s21(self):
        return self._s21s

    @property
    def s12(self):
        return self._s12s

    @property
    def s11(self):
        return self._s11s

    @property
    def s22(self):
        return self._s22s

    @property
    def vswr_in(self):
        return self._vswr_in

    @property
    def vswr_out(self):
        return self._vswr_out

    @property
    def phase(self):
        return self._s21s_ph

    @property
    def s21_phase_norm(self):
        return self._s21s_ph_norm

    @property
    def phase_err(self):
        return self._s21s_ph_err

    @property
    def phase_rmse(self):
        return self._s21s_ph_rmse

    @property
    def s21_err(self):
        return self._s21s_err

    @property
    def s21_rmse(self):
        return self._s21s_rmse

    @property
    def misc(self):
        return self._misc

    @property
    def adjust_set(self):
        return self._adjust_dir

    @adjust_set.setter
    def adjust_set(self, value):
        self._adjust_dir = self.adjust_dirs[value]

    @property
    def stats(self):
        low = self._min_freq_index
        high = self._max_freq_index
        mid = low + (high - low) // 2
        f1 = round(self.freqs[low] / 1_000_000_000, 2)
        f2 = round(self.freqs[mid] / 1_000_000_000, 2)
        f3 = round(self.freqs[high] / 1_000_000_000, 2)

        kp_freq_min = f'{self._kp_freq_min:.02f} ГГц' if self._kp_freq_min != 'n/a' else 'n/a'
        kp_freq_max = f'{self._kp_freq_max:.02f} ГГц' if self._kp_freq_max != 'n/a' else 'n/a'

#         return f'''Потери, минимум:
# {self._s21_mins[0]:.02f} дБ на {f1} ГГц
# {self._s21_mins[1]:.02f} дБ на {f2} ГГц
# {self._s21_mins[2]:.02f} дБ на {f3} ГГц
#
# КСВ вх, макс:
# {self._vswr_in_max[0]:.02f} на {f1} ГГц
# {self._vswr_in_max[1]:.02f} на {f2} ГГц
# {self._vswr_in_max[2]:.02f} на {f3} ГГц
#
# КСВ вых, макс:
# {self._vswr_out_max[0]:.02f} на {f1} ГГц
# {self._vswr_out_max[1]:.02f} на {f2} ГГц
# {self._vswr_out_max[2]:.02f} на {f3} ГГц
#
# φ, ошибка:
# {self._phase_err_max[0]:.02f} град на {f1} ГГц
# {self._phase_err_max[1]:.02f} град на {f2} ГГц
# {self._phase_err_max[2]:.02f} град на {f3} ГГц
#
# φ, СКО:
# {self._phase_rmse_values[0]:.02f} град на {f1} ГГц
# {self._phase_rmse_values[1]:.02f} град на {f2} ГГц
# {self._phase_rmse_values[2]:.02f} град на {f3} ГГц
#
# Потери, ошибка:
# {self._s21_err_max[0]:.02f} дБ на {f1} ГГц
# {self._s21_err_max[1]:.02f} дБ на {f2} ГГц
# {self._s21_err_max[2]:.02f} дБ на {f3} ГГц
#
# Потери, СКО:
# {self._s21_rmse_values[0]:.02f} дБ на {f1} ГГц
# {self._s21_rmse_values[1]:.02f} дБ на {f2} ГГц
# {self._s21_rmse_values[2]:.02f} дБ на {f3} ГГц
#
# Нижняя граница РЧ, Fн:
# {kp_freq_min}
#
# Верхняя граница РЧ, Fв:
# {kp_freq_max}
# '''
        return f'''Потери, минимум:
{self._s21_mins[0]:.02f} дБ на {f1} ГГц
{self._s21_mins[1]:.02f} дБ на {f2} ГГц
{self._s21_mins[2]:.02f} дБ на {f3} ГГц

Нижняя граница РЧ, Fн:
{kp_freq_min}

Верхняя граница РЧ, Fв:
{kp_freq_max}
'''
