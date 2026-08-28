' Roda numa thread separada da UI (Task) — bloquear aqui é seguro,
' não trava a tela nem o controle remoto, mesmo se o backend não responder.

Function BaseUrl() as String
    return "http://192.168.18.4:8000"
End Function

Sub Init()
    m.top.functionName = "DoFetch"
End Sub

Function HttpGetJson(caminho as String) as Dynamic
    http = CreateObject("roUrlTransfer")
    port = CreateObject("roMessagePort")
    http.SetMessagePort(port)
    http.SetUrl(BaseUrl() + caminho)

    if not http.AsyncGetToString()
        return invalid
    end if

    msg = wait(5000, port)
    if msg = invalid
        http.AsyncCancel()
        return invalid
    end if

    if type(msg) = "roUrlEvent" and msg.GetResponseCode() = 200
        return ParseJson(msg.GetString())
    end if

    return invalid
End Function

Sub DoFetch()
    sucesso = false

    ranking = HttpGetJson("/api/ranking?periodo=semana")
    if ranking <> invalid
        m.top.ranking = ranking
        sucesso = true
    end if

    tempo = HttpGetJson("/api/tempo?periodo=semana")
    if tempo <> invalid
        m.top.tempo = tempo
        sucesso = true
    end if

    tempoPessoa = HttpGetJson("/api/tempo/pessoa?periodo=semana")
    if tempoPessoa <> invalid
        m.top.tempoPessoa = tempoPessoa
        sucesso = true
    end if

    semana = HttpGetJson("/api/tarefas/calendario?periodo=semana")
    if semana <> invalid
        m.top.semana = semana
        sucesso = true
    end if

    exercicioRanking = HttpGetJson("/api/exercicios/ranking?periodo=semana")
    if exercicioRanking <> invalid
        m.top.exercicioRanking = exercicioRanking
        sucesso = true
    end if

    exercicioTipo = HttpGetJson("/api/exercicios/tempo-por-tipo?periodo=semana")
    if exercicioTipo <> invalid
        m.top.exercicioTipo = exercicioTipo
        sucesso = true
    end if

    semanaExercicio = HttpGetJson("/api/exercicios/calendario?periodo=semana")
    if semanaExercicio <> invalid
        m.top.semanaExercicio = semanaExercicio
        sucesso = true
    end if

    m.top.ok = sucesso
End Sub
