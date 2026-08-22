from django.http import JsonResponse


async def healthz(_: object) -> JsonResponse:
    return JsonResponse({"status": "ok"})
