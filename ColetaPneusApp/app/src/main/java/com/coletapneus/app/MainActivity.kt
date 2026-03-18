package com.coletapneus.app

import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.widget.Button
import android.widget.Toast

/**
 * Tela inicial do aplicativo
 * Responsabilidade: Apresentar opções de navegação para cliente ou prestador
 * Segue princípios de responsabilidade única (Fábio Akita aprova)
 */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Inicializa componentes da tela
        val btnCliente = findViewById<Button>(R.id.btn_sou_cliente)
        val btnPrestador = findViewById<Button>(R.id.btn_sou_prestador)

        // Define ações dos botões (com feedback claro)
        btnCliente.setOnClickListener {
            mostrarFeedback("Navegando para área do cliente...")
            // Implementar navegação para tela de cliente futuramente
        }

        btnPrestador.setOnClickListener {
            mostrarFeedback("Navegando para área do prestador...")
            // Implementar navegação para tela de prestador futuramente
        }
    }

    /**
     * Método auxiliar para mostrar feedback ao usuário
     * Evita duplicação de código (princípio DRY)
     */
    private fun mostrarFeedback(mensagem: String) {
        Toast.makeText(this, mensagem, Toast.LENGTH_SHORT).show()
    }
}
