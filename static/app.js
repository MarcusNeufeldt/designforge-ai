new Vue({
    el: '#app',
    data: {
        prompt: '',
        results: [],
        isLoading: false,
        availableLLMs: [],
        selectedLLMs: [],
        promptHistory: [],
        codeVisible: {},
        showReiterationModal: false,
        reiterationLLM: '',
        reiterationPrompt: '',
        reiterationPreviousContent: '',
        showHtmlInjectionModal: false,
        showHtmlPreviewModal: false,
        injectedHtml: '',
        showFullScreenModal: false,
        fullScreenContent: null,
        fetchingLLMs: false,
        llmFetchError: null,
    },
    mounted() {
        this.fetchLLMs();
        this.fetchPromptHistory();
    },
    methods: {
        async fetchLLMs() {
            this.fetchingLLMs = true;
            this.llmFetchError = null;
            try {
                const response = await axios.get('/api/llms');
                this.availableLLMs = response.data;
                if (this.availableLLMs.length === 0) {
                    this.llmFetchError = "No models were fetched from OpenRouter. Please check your API key and try again.";
                }
                this.$nextTick(() => {
                    this.initializeSelect2();
                });
            } catch (error) {
                console.error('Error fetching LLMs:', error);
                this.llmFetchError = "An error occurred while fetching the models. Please try again later.";
            } finally {
                this.fetchingLLMs = false;
            }
        },
        initializeSelect2() {
            const self = this;
            $('#llm-select').select2({
                placeholder: 'Select LLMs',
                width: '100%',
                tags: true,
                tokenSeparators: [',', ' '],
                maximumSelectionLength: 5,
                language: {
                    maximumSelected: function (e) {
                        return "You can only select up to " + e.maximum + " LLMs";
                    }
                }
            }).on('change', function() {
                self.selectedLLMs = $(this).val();
            });
        },
        async fetchPromptHistory() {
            try {
                const response = await axios.get('/api/prompt_history');
                this.promptHistory = response.data;
            } catch (error) {
                console.error('Error fetching prompt history:', error);
            }
        },
        setPrompt(prompt) {
            this.prompt = prompt;
        },
        async compare() {
            if (this.selectedLLMs.length === 0) {
                alert('Please select at least one LLM.');
                return;
            }
            this.isLoading = true;
            try {
                const response = await axios.post('/api/compare', {
                    prompt: this.prompt,
                    selected_llms: this.selectedLLMs,
                    injected_html: this.injectedHtml
                });
                this.results = response.data.results;
                this.codeVisible = Object.fromEntries(this.results.map((_, index) => [index, false]));
                await this.fetchPromptHistory();
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred while comparing LLMs');
            } finally {
                this.isLoading = false;
            }
        },
        toggleCode(index) {
            this.$set(this.codeVisible, index, !this.codeVisible[index]);
        },
        copyCode(code) {
            navigator.clipboard.writeText(code).then(() => {
                alert('Code copied to clipboard!');
            }).catch(err => {
                console.error('Failed to copy code: ', err);
            });
        },
        openReiterationModal(llm, previousContent) {
            this.showReiterationModal = true;
            this.reiterationLLM = llm;
            this.reiterationPreviousContent = previousContent;
        },
        closeReiterationModal() {
            this.showReiterationModal = false;
            this.reiterationPrompt = '';
        },
        async reiterate() {
            this.isLoading = true;
            this.showReiterationModal = false;
            try {
                const response = await axios.post('/api/reiterate', {
                    original_prompt: this.prompt,
                    changes_prompt: this.reiterationPrompt,
                    llm: this.reiterationLLM,
                    previous_content: this.reiterationPreviousContent,
                    injected_html: this.injectedHtml
                });
                const newResult = response.data.result;
                const index = this.results.findIndex(r => r.llm === this.reiterationLLM);
                if (index !== -1) {
                    this.$set(this.results, index, newResult);
                } else {
                    this.results.push(newResult);
                }
                this.codeVisible = Object.fromEntries(this.results.map((_, index) => [index, false]));
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred while reiterating with the LLM');
            } finally {
                this.isLoading = false;
                this.reiterationPrompt = '';
            }
        },
        openHtmlInjectionModal() {
            this.showHtmlInjectionModal = true;
        },
        closeHtmlInjectionModal() {
            this.showHtmlInjectionModal = false;
        },
        injectHtml() {
            this.closeHtmlInjectionModal();
        },
        previewInjectedHtml() {
            if (this.injectedHtml) {
                this.showHtmlPreviewModal = true;
            }
        },
        closeHtmlPreviewModal() {
            this.showHtmlPreviewModal = false;
        },
        openFullScreenView(result) {
            this.fullScreenContent = result;
            this.showFullScreenModal = true;
        },
        closeFullScreenView() {
            this.showFullScreenModal = false;
            this.fullScreenContent = null;
        },
        deleteResult(index) {
            this.results.splice(index, 1);
            this.codeVisible = Object.fromEntries(this.results.map((_, index) => [index, this.codeVisible[index] || false]));
        }
    }
});