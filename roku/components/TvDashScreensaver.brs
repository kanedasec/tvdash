' ==== Paleta ====
' Fundo levemente aquecido (não preto puro), texto quente, e uma cor fixa por
' pessoa que se repete em todos os gráficos (identidade consistente), separada
' das cores de "seção" (as tabs ao lado de cada título).
Function CorTextoPrimario() as String
    return "0xEDEAE4FF"
End Function

Function CorTextoMuted() as String
    return "0x8B8F9BFF"
End Function

Function CorPessoa(nome as String) as String
    n = LCase(nome)
    if Instr(1, n, "vernon") > 0 then return "0xE08B4FFF"  ' terracota
    if Instr(1, n, "luana") > 0 then return "0x6FA8A0FF"   ' verde-sálvia
    fallback = ["0xC9A66BFF", "0xB97A87FF", "0x9B8EC4FF"]
    soma = 0
    for i = 1 to Len(n)
        soma = soma + Asc(Mid(n, i, 1))
    end for
    return fallback[soma MOD fallback.Count()]
End Function

Function CorAtividade(indice as Integer) as String
    ' Escala monocromática (mesmo tom da tab "Tempo por atividade"), do mais claro
    ' pro mais escuro — comunica ranking sem virar um arco-íris genérico de gráfico.
    cores = ["0x8FADD6FF", "0x6C8EBFFF", "0x5474A0FF", "0x415A80FF", "0x304563FF"]
    return cores[indice MOD cores.Count()]
End Function

Sub Init()
    m.top.backgroundColor = "0x14161CFF"
    m.menuAtual = 0 ' 0 = casa, 1 = exercicio

    m.lblTitulo = m.top.findNode("lblTitulo")
    AplicarFonte(m.lblTitulo, 40, true)
    m.lblTitulo.text = "TV Dash - Casa"

    m.lblRelogio = m.top.findNode("lblRelogio")
    AplicarFonte(m.lblRelogio, 30, false)

    m.lblStatus = m.top.findNode("lblStatus")
    AplicarFonte(m.lblStatus, 22, false)

    AplicarFonte(m.top.findNode("tituloSemana"), 28, true)
    AplicarFonte(m.top.findNode("tituloPontos"), 26, true)
    AplicarFonte(m.top.findNode("tituloTempoPessoa"), 26, true)
    AplicarFonte(m.top.findNode("tituloTempoAtividade"), 26, true)

    AplicarFonte(m.top.findNode("tituloSemanaEx"), 28, true)
    AplicarFonte(m.top.findNode("tituloTempoPessoaEx"), 26, true)
    AplicarFonte(m.top.findNode("tituloCheckinsEx"), 26, true)
    AplicarFonte(m.top.findNode("tituloTipoEx"), 26, true)

    m.menuCasa = m.top.findNode("menuCasa")
    m.menuExercicio = m.top.findNode("menuExercicio")

    m.grpSemana = m.top.findNode("grpSemana")
    m.grpPontos = m.top.findNode("grpPontos")
    m.grpTempoPessoa = m.top.findNode("grpTempoPessoa")
    m.grpTempoAtividade = m.top.findNode("grpTempoAtividade")

    m.grpSemanaEx = m.top.findNode("grpSemanaEx")
    m.grpExercicioTempo = m.top.findNode("grpExercicioTempo")
    m.grpExercicioCheckins = m.top.findNode("grpExercicioCheckins")
    m.grpExercicioTipo = m.top.findNode("grpExercicioTipo")

    ' Busca de dados roda numa Task separada — nunca trava a tela/controle remoto,
    ' mesmo se o backend estiver fora do ar ou a rede travar.
    m.tarefaBusca = CreateObject("roSGNode", "DataFetcherTask")
    m.tarefaBusca.ObserveField("ok", "OnDadosRecebidos")

    m.refreshTimer = m.top.findNode("refreshTimer")
    m.refreshTimer.ObserveField("fire", "OnRefreshTimer")
    m.refreshTimer.control = "start"

    m.rotateTimer = m.top.findNode("rotateTimer")
    m.rotateTimer.ObserveField("fire", "OnRotateTimer")
    m.rotateTimer.control = "start"

    AtualizarRelogio()
    DispararBusca()
End Sub

' Criar um roSGNode "Font" manualmente e atribuir a .font não funciona nesse firmware
' (o Label fica sem renderizar nenhum texto). Atribuir a string da fonte de sistema
' direto no campo .font do Label funciona — o Roku converte automaticamente.
Sub AplicarFonte(lbl as Object, tamanho as Integer, negrito as Boolean)
    if negrito
        lbl.font = "font:MediumBoldSystemFont"
    else
        lbl.font = "font:MediumSystemFont"
    end if
    lbl.font.size = tamanho
End Sub

Sub OnRefreshTimer()
    AtualizarRelogio()
    DispararBusca()
End Sub

Sub OnRotateTimer()
    if m.menuAtual = 0
        m.menuAtual = 1
        m.menuCasa.visible = false
        m.menuExercicio.visible = true
        m.lblTitulo.text = "TV Dash - Exercicios"
    else
        m.menuAtual = 0
        m.menuExercicio.visible = false
        m.menuCasa.visible = true
        m.lblTitulo.text = "TV Dash - Casa"
    end if
End Sub

Sub AtualizarRelogio()
    dt = CreateObject("roDateTime")
    dt.ToLocalTime()
    m.lblRelogio.text = Formata2(dt.GetHours()) + ":" + Formata2(dt.GetMinutes())
End Sub

Function Formata2(n as Integer) as String
    if n < 10
        return "0" + n.ToStr()
    end if
    return n.ToStr()
End Function

Sub DispararBusca()
    ' Garante que não fica rodando duas buscas em paralelo se o timer disparar de novo antes da anterior terminar.
    m.tarefaBusca.control = "stop"
    m.tarefaBusca.control = "RUN"
End Sub

Sub OnDadosRecebidos(event as Object)
    tarefa = event.GetRoSGNode()
    sucesso = event.GetData()

    if sucesso
        if tarefa.semana <> invalid then RenderSemana(m.grpSemana, tarefa.semana)
        if tarefa.ranking <> invalid then RenderPontosPercentual(m.grpPontos, tarefa.ranking)
        if tarefa.tempoPessoa <> invalid
            RenderBarList(m.grpTempoPessoa, tarefa.tempoPessoa, "nome", "minutos_totais", " min", "pessoa")
        end if
        if tarefa.tempo <> invalid
            RenderBarList(m.grpTempoAtividade, tarefa.tempo, "nome", "minutos_totais", " min", "atividade")
        end if

        if tarefa.semanaExercicio <> invalid then RenderSemanaExercicio(m.grpSemanaEx, tarefa.semanaExercicio)
        if tarefa.exercicioRanking <> invalid
            RenderBarList(m.grpExercicioTempo, tarefa.exercicioRanking, "nome", "minutos_totais", " min", "pessoa")
            RenderBarList(
                m.grpExercicioCheckins, OrdenarDesc(tarefa.exercicioRanking, "checkins"), "nome", "checkins", " chk", "pessoa"
            )
        end if
        if tarefa.exercicioTipo <> invalid
            RenderBarList(m.grpExercicioTipo, tarefa.exercicioTipo, "nome", "minutos_totais", " min", "atividade")
        end if

        m.lblStatus.text = "atualizado as " + m.lblRelogio.text
        m.lblStatus.color = CorTextoMuted()
    else
        m.lblStatus.text = "sem conexao com o servidor TV Dash"
        m.lblStatus.color = "0xC97A6EFF"
    end if
End Sub

Sub LimparFilhos(grupo as Object)
    filhos = grupo.GetChildren(-1, 0)
    if filhos.Count() > 0
        grupo.RemoveChildren(filhos)
    end if
End Sub

Function TruncarTexto(s as String, maxLen as Integer) as String
    if Len(s) > maxLen
        return Left(s, maxLen) + "..."
    end if
    return s
End Function

' Ordena uma cópia do array (bubble sort simples — os arrays aqui são de 2-3 pessoas,
' não precisa de nada mais sofisticado) por um campo numérico, decrescente.
Function OrdenarDesc(itens as Object, campo as String) as Object
    copia = []
    for each item in itens
        copia.push(item)
    end for
    for i = 0 to copia.Count() - 2
        for j = 0 to copia.Count() - 2 - i
            if copia[j][campo] < copia[j + 1][campo]
                tmp = copia[j]
                copia[j] = copia[j + 1]
                copia[j + 1] = tmp
            end if
        end for
    end for
    return copia
End Function

' Calendário da semana (tarefas de casa): uma coluna por dia (segunda a domingo), com
' as tarefas concluídas/planejadas e os compromissos daquele dia. O dia de hoje recebe
' um destaque sutil de fundo.
Sub RenderSemana(grupo as Object, dias as Object)
    LimparFilhos(grupo)

    dt = CreateObject("roDateTime")
    dt.ToLocalTime()
    hojeStr = Formata2(dt.GetDayOfMonth()) + "/" + Formata2(dt.GetMonth())

    larguraColuna = 257
    for i = 0 to dias.Count() - 1
        dia = dias[i]
        x = i * larguraColuna

        if dia.data = hojeStr
            destaque = CreateObject("roSGNode", "Rectangle")
            destaque.translation = [x - 10, -10]
            destaque.width = larguraColuna - 12
            destaque.height = 330
            destaque.color = "0x1E222BFF"
            grupo.appendChild(destaque)
        end if

        AdicionarLabel(grupo, dia.dia_semana + " " + dia.data, x, 0, CorTextoPrimario(), 22, true)

        y = 44
        for each item in dia.tarefas
            if item.status = "feita"
                prefixo = "[x] "
                cor = "0x6FA8A0FF"
            else
                prefixo = "[ ] "
                cor = CorTextoMuted()
            end if
            AdicionarLabel(grupo, prefixo + TruncarTexto(item.nome, 18), x, y, cor, 18, false)
            y = y + 32
        end for
        for each comp in dia.compromissos
            texto = comp.hora + " " + TruncarTexto(comp.titulo, 16)
            AdicionarLabel(grupo, texto, x, y, "0xFFB75EFF", 18, false)
            y = y + 32
        end for
    end for
End Sub

' Calendário da semana (exercícios): uma coluna por dia, listando os checkins
' (pessoa: tipo (duração)).
Sub RenderSemanaExercicio(grupo as Object, dias as Object)
    LimparFilhos(grupo)

    dt = CreateObject("roDateTime")
    dt.ToLocalTime()
    hojeStr = Formata2(dt.GetDayOfMonth()) + "/" + Formata2(dt.GetMonth())

    larguraColuna = 257
    for i = 0 to dias.Count() - 1
        dia = dias[i]
        x = i * larguraColuna

        if dia.data = hojeStr
            destaque = CreateObject("roSGNode", "Rectangle")
            destaque.translation = [x - 10, -10]
            destaque.width = larguraColuna - 12
            destaque.height = 330
            destaque.color = "0x1E222BFF"
            grupo.appendChild(destaque)
        end if

        AdicionarLabel(grupo, dia.dia_semana + " " + dia.data, x, 0, CorTextoPrimario(), 22, true)

        y = 44
        for each c in dia.checkins
            texto = c.pessoa + ": " + TruncarTexto(c.tipo, 13) + " (" + c.duracao_min.ToStr() + "m)"
            AdicionarLabel(grupo, texto, x, y, CorPessoa(c.pessoa), 16, false)
            y = y + 28
        end for
    end for
End Sub

' Barra segmentada mostrando a proporção de pontos de cada pessoa (substitui um
' gráfico de pizza, que não é viável de desenhar nativamente em SceneGraph).
Sub RenderPontosPercentual(grupo as Object, ranking as Object)
    LimparFilhos(grupo)

    total = 0
    for each item in ranking
        total = total + item.pontos
    end for

    if total = 0
        AdicionarLabel(grupo, "Sem pontos ainda essa semana", 0, 0, CorTextoMuted(), 22, false)
        return
    end if

    larguraTotal = 540
    x = 0
    for each item in ranking
        largura = (item.pontos / total) * larguraTotal
        if item.pontos > 0 and largura < 3 then largura = 3
        if largura > 0
            seg = CreateObject("roSGNode", "Rectangle")
            seg.translation = [x, 0]
            seg.width = largura
            seg.height = 44
            seg.color = CorPessoa(item.nome)
            grupo.appendChild(seg)
        end if
        x = x + largura
    end for

    y = 70
    for each item in ranking
        pct = Int(((item.pontos / total) * 100) + 0.5)

        swatch = CreateObject("roSGNode", "Rectangle")
        swatch.translation = [0, y + 4]
        swatch.width = 22
        swatch.height = 22
        swatch.color = CorPessoa(item.nome)
        grupo.appendChild(swatch)

        AdicionarLabel(grupo, item.nome + ": " + pct.ToStr() + "%", 36, y, CorTextoPrimario(), 22, false)

        y = y + 46
    end for
End Sub

Sub RenderBarList(conteudo as Object, itens as Object, campoNome as String, campoValor as String, sufixo as String, modoCor as String)
    LimparFilhos(conteudo)

    if itens.Count() = 0
        AdicionarLabel(conteudo, "Sem dados ainda", 0, 0, CorTextoMuted(), 22, false)
        return
    end if

    maxValor = 1
    for each item in itens
        if item[campoValor] > maxValor then maxValor = item[campoValor]
    end for

    larguraNomeCol = 170
    larguraMaxBarra = 260
    y = 0
    contador = 0
    for each item in itens
        if contador >= 6 then exit for

        nome = item[campoNome]
        valor = item[campoValor]
        largura = 10 + ((valor / maxValor) * (larguraMaxBarra - 10))

        if modoCor = "pessoa"
            cor = CorPessoa(nome)
        else
            cor = CorAtividade(contador)
        end if

        AdicionarLabel(conteudo, TruncarTexto(nome, 16), 0, y, CorTextoPrimario(), 22, false)

        barra = CreateObject("roSGNode", "Rectangle")
        barra.translation = [larguraNomeCol, y + 4]
        barra.width = largura
        barra.height = 26
        barra.color = cor
        conteudo.appendChild(barra)

        AdicionarLabel(conteudo, valor.ToStr() + sufixo, larguraNomeCol + larguraMaxBarra + 16, y, CorTextoMuted(), 20, false)

        y = y + 60
        contador = contador + 1
    end for
End Sub

Sub AdicionarLabel(pai as Object, texto as String, x as Integer, y as Integer, cor as String, tamanho as Integer, negrito as Boolean)
    lbl = CreateObject("roSGNode", "Label")
    lbl.text = texto
    lbl.translation = [x, y]
    lbl.color = cor
    AplicarFonte(lbl, tamanho, negrito)
    pai.appendChild(lbl)
End Sub
