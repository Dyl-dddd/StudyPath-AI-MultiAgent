import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'katex/dist/katex.min.css'
import './styles/main.css'
import './styles/sidebar-v2.css'
import App from './App.vue'
import router from './router'

createApp(App).use(createPinia()).use(router).mount('#app')
