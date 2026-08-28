' Copie este arquivo para config.brs antes de gerar o pacote.
' config.brs é ignorado pelo Git porque contém a chave privada da Roku.

Function TvdashBaseUrl() as String
    return "https://tvdash.example.com"
End Function

Function TvdashApiKey() as String
    return "replace-with-the-same-roku-api-key-used-on-the-vps"
End Function
