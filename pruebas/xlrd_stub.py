"""
Stub de pruebas que imita la API de xlrd que usa bank_io.

Permite probar la ruta del .xls BIFF sin tener la librería instalada. Los datos
son inventados a propósito: este fichero se reparte con el programa, así que no
puede llevar movimientos de nadie.
"""
XL_CELL_EMPTY, XL_CELL_TEXT, XL_CELL_NUMBER = 0, 1, 2
XL_CELL_DATE, XL_CELL_BOOLEAN, XL_CELL_ERROR, XL_CELL_BLANK = 3, 4, 5, 6


class XLDateError(Exception):
    pass


class Cell:
    def __init__(self, ctype, value):
        self.ctype, self.value = ctype, value


T, N, D, E = XL_CELL_TEXT, XL_CELL_NUMBER, XL_CELL_DATE, XL_CELL_EMPTY

FILAS = [
    [(T, "BANCO FICTICIO - EXTRACTO"), (E, ""), (E, ""), (E, "")],
    [(T, "Cuenta ES00 0000"), (E, ""), (E, ""), (E, "")],
    [(E, ""), (E, ""), (E, ""), (E, "")],
    [(T, "Fecha operación"), (T, "Fecha valor"), (T, "Concepto"), (T, "Importe")],
    [(D, 46114.0), (D, 46114.0), (T, "NOMINA EMPRESA FICTICIA SL"), (N, 2000.0)],
    [(D, 46117.0), (D, 46117.0), (T, "COMPRA MERCADONA MADRID"), (N, -60.0)],
    [(D, 46120.0), (D, 46120.0), (T, "MEDIA MARKT ONLINE"), (N, -350.0)],
    [(D, 46122.0), (D, 46122.0), (T, "SUPERMERCADOS DIA MADRID"), (N, -40.0)],
    [(D, 46124.0), (D, 46124.0), (T, "BAR LA ESQUINA"), (N, -18.0)],
    [(D, 46126.0), (D, 46126.0), (T, "GUARDIA CIVIL MULTA"), (N, -100.0)],
    [(D, 46128.0), (D, 46128.0), (T, "SEGURO DE VIDA MAPFRE"), (N, -30.0)],
    [(D, 46130.0), (D, 46130.0), (T, "BP OIL ESPANA"), (N, -60.0)],
]


class Sheet:
    name = "Movimientos"
    nrows = len(FILAS)
    ncols = 4

    def cell(self, r, c):
        return Cell(*FILAS[r][c])


class Book:
    datemode = 0

    def sheets(self):
        return [Sheet()]


def open_workbook(ruta, formatting_info=False, on_demand=False):
    return Book()


def xldate_as_tuple(valor, datemode):
    import datetime
    base = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=float(valor))
    return (base.year, base.month, base.day, base.hour, base.minute, base.second)
