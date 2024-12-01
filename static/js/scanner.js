class BarcodeScanner {
    constructor() {
        this.stream = null;
        this.activeCamera = 'environment';
        this.scanStep = 1;
        this.firstBarcode = null;
    }

    async startScanning(videoElement, resultCallback, validateCallback) {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: this.activeCamera }
            });
            
            videoElement.srcObject = this.stream;
            
            if ('BarcodeDetector' in window) {
                const barcodeDetector = new BarcodeDetector({
                    formats: ['qr_code', 'ean_13', 'ean_8', 'code_128']
                });
                
                const detectLoop = async () => {
                    try {
                        const barcodes = await barcodeDetector.detect(videoElement);
                        if (barcodes.length > 0) {
                            const barcode = barcodes[0].rawValue;
                            if (await validateCallback(barcode, this.scanStep)) {
                                resultCallback(barcode, this.scanStep);
                            }
                        }
                    } catch (error) {
                        console.error('Barcode Erkennungsfehler:', error);
                    }
                    
                    if (this.stream) {
                        requestAnimationFrame(detectLoop);
                    }
                };
                
                requestAnimationFrame(detectLoop);
            }
        } catch (error) {
            console.error('Kamera Zugriffsfehler:', error);
            throw error;
        }
    }

    stopScanning() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    }

    switchCamera() {
        this.activeCamera = this.activeCamera === 'environment' ? 'user' : 'environment';
        this.stopScanning();
        // Neustart des Scanners mit neuer Kamera
    }
} 