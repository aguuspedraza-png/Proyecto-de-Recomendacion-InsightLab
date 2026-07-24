# ======================================================================================
# TESTS AUTOMATIZADOS - API INSIGHTLAB
# ======================================================================================
# Estos tests validan que los endpoints de la API respondan correctamente antes de
# cada despliegue. Se ejecutan con pytest:
#
#     pytest tests/ -v
#
# Se usa TestClient de FastAPI, que levanta la API en memoria: no hace falta tener
# el servidor corriendo con uvicorn para correr los tests.
# ======================================================================================

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Se agrega la carpeta src/ al path para poder importar api.py, sin importar desde
# donde se ejecuten los tests.
SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC_DIR)

from api import app  # noqa: E402

client = TestClient(app)


# ----------------------------------------------------------------------
# DATOS DE PRUEBA
# ----------------------------------------------------------------------
# Sesion valida de ejemplo, con las 17 variables que espera el esquema SesionUsuario.
SESION_VALIDA = {
    "device_type": 1,
    "user_type": 1,
    "marketing_channel": 2,
    "product_category": 4,
    "unit_price": 1200.0,
    "quantity": 1,
    "discount_percent": 10.0,
    "discount_amount": 120.0,
    "pages_viewed": 12,
    "time_on_site_sec": 600.0,
    "added_to_cart": 1,
    "payment_method": 0,
    "visit_day": 15,
    "visit_month": 3,
    "visit_weekday": 4,
    "visit_season": 1,
    "location": 45,
}


# ======================================================================================
# TESTS DEL ENDPOINT RAIZ
# ======================================================================================

def test_raiz_responde_ok():
    """El endpoint de verificacion debe responder con codigo 200."""
    respuesta = client.get("/")
    assert respuesta.status_code == 200


def test_raiz_informa_estado_de_los_componentes():
    """El endpoint raiz debe informar si el preprocesador, el modelo y el motor
    de recomendacion se cargaron correctamente."""
    datos = client.get("/").json()

    assert "preprocesador_cargado" in datos
    assert "modelo_cargado" in datos
    assert "motor_recomendacion_cargado" in datos

    # Los tres componentes deben estar disponibles para que la API sea util.
    assert datos["preprocesador_cargado"] is True
    assert datos["modelo_cargado"] is True
    assert datos["motor_recomendacion_cargado"] is True


# ======================================================================================
# TESTS DEL ENDPOINT /predict
# ======================================================================================

def test_predict_responde_ok_con_datos_validos():
    """Con una sesion valida, /predict debe responder con codigo 200."""
    respuesta = client.post("/predict", json=SESION_VALIDA)
    assert respuesta.status_code == 200


def test_predict_devuelve_la_estructura_esperada():
    """La respuesta de /predict debe incluir la prediccion, el booleano de compra
    y la probabilidad."""
    datos = client.post("/predict", json=SESION_VALIDA).json()

    assert "prediccion" in datos
    assert "compra" in datos
    assert "probabilidad_compra" in datos


def test_predict_devuelve_valores_validos():
    """La prediccion debe ser 0 o 1, y la probabilidad debe estar entre 0 y 1."""
    datos = client.post("/predict", json=SESION_VALIDA).json()

    assert datos["prediccion"] in (0, 1)
    assert isinstance(datos["compra"], bool)
    assert 0.0 <= datos["probabilidad_compra"] <= 1.0


def test_predict_coherencia_entre_prediccion_y_compra():
    """El campo 'compra' debe ser coherente con el valor de 'prediccion'."""
    datos = client.post("/predict", json=SESION_VALIDA).json()
    assert datos["compra"] == (datos["prediccion"] == 1)


def test_predict_rechaza_datos_incompletos():
    """Si falta alguna variable obligatoria, la API debe rechazar la peticion
    con un error de validacion (422), en lugar de devolver un resultado incorrecto."""
    sesion_incompleta = SESION_VALIDA.copy()
    del sesion_incompleta["unit_price"]

    respuesta = client.post("/predict", json=sesion_incompleta)
    assert respuesta.status_code == 422


def test_predict_rechaza_tipos_invalidos():
    """Si una variable llega con un tipo que no corresponde, la API debe rechazarla."""
    sesion_invalida = SESION_VALIDA.copy()
    sesion_invalida["pages_viewed"] = "muchas"

    respuesta = client.post("/predict", json=sesion_invalida)
    assert respuesta.status_code == 422


def test_predict_rechaza_paginas_vistas_en_cero():
    """pages_viewed se usa para derivar tiempo_por_pagina, por lo que no puede ser 0.
    El esquema lo define con la restriccion gt=0."""
    sesion_invalida = SESION_VALIDA.copy()
    sesion_invalida["pages_viewed"] = 0

    respuesta = client.post("/predict", json=sesion_invalida)
    assert respuesta.status_code == 422


# ======================================================================================
# TESTS DEL ENDPOINT /recommend
# ======================================================================================

def test_recommend_responde_ok_con_datos_validos():
    """Con una sesion valida, /recommend debe responder con codigo 200."""
    respuesta = client.post("/recommend", json=SESION_VALIDA)
    assert respuesta.status_code == 200


def test_recommend_devuelve_la_estructura_esperada():
    """La respuesta de /recommend debe incluir la probabilidad, la prediccion,
    la intencion de compra y la accion sugerida."""
    datos = client.post("/recommend", json=SESION_VALIDA).json()

    assert "purchase_probability" in datos
    assert "purchase_prediction" in datos
    assert "purchase_intention" in datos
    assert "actions" in datos
    assert "action_details" in datos


def test_recommend_devuelve_valores_validos():
    """La probabilidad debe estar entre 0 y 1, y la prediccion debe ser 0 o 1."""
    datos = client.post("/recommend", json=SESION_VALIDA).json()

    assert 0.0 <= datos["purchase_probability"] <= 1.0
    assert datos["purchase_prediction"] in (0, 1)


def test_recommend_siempre_sugiere_una_accion():
    """El motor debe devolver una accion incluso cuando ninguna regla de asociacion
    coincide con la sesion, para que el sistema nunca quede sin recomendacion."""
    datos = client.post("/recommend", json=SESION_VALIDA).json()

    assert datos["actions"] is not None
    assert isinstance(datos["actions"], str)
    assert len(datos["actions"]) > 0


def test_recommend_rechaza_datos_incompletos():
    """Al igual que /predict, /recommend debe validar los datos de entrada."""
    sesion_incompleta = SESION_VALIDA.copy()
    del sesion_incompleta["device_type"]

    respuesta = client.post("/recommend", json=sesion_incompleta)
    assert respuesta.status_code == 422


# ======================================================================================
# TESTS DE COHERENCIA ENTRE ENDPOINTS
# ======================================================================================

def test_predict_y_recommend_coinciden_en_la_probabilidad():
    """Ambos endpoints usan el mismo modelo y el mismo preprocesador, por lo que
    para una misma sesion deben devolver la misma probabilidad de compra.

    Nota: /recommend devuelve la probabilidad redondeada a dos decimales, mientras
    que /predict devuelve el valor completo. Por eso la comparacion se hace con
    esa tolerancia."""
    prob_predict = client.post("/predict", json=SESION_VALIDA).json()["probabilidad_compra"]
    prob_recommend = client.post("/recommend", json=SESION_VALIDA).json()["purchase_probability"]

    assert round(prob_predict, 2) == pytest.approx(prob_recommend, abs=0.01)


def test_predict_y_recommend_coinciden_en_la_prediccion():
    """Al usar el mismo modelo, la prediccion binaria debe ser identica en ambos
    endpoints para una misma sesion."""
    pred_predict = client.post("/predict", json=SESION_VALIDA).json()["prediccion"]
    pred_recommend = client.post("/recommend", json=SESION_VALIDA).json()["purchase_prediction"]

    assert pred_predict == pred_recommend