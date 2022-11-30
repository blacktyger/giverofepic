$('#walletAddress').on('input', async function() {
    let address = $('#walletAddress').val()
    let addrText = $('.addressFeedback')
    let addrIcon = $('.addressIcon')
    let button = $('#sendTransactionButton')

    if (!address) {
        addrIcon.css('color', 'grey')
        button.attr('disabled', true)
        addrText.text('')
    } else {
        if (address.trim().length === 52) {
        addrIcon.css('color', 'green')
            button.attr('disabled', false)
            addrText.text('')
        } else {
        addrIcon.css('color', 'orange')
            button.attr('disabled', true)
            addrText.text(`* Invalid wallet address`)
        }
    }
});



// Listen for algorithm select changes
$('#algorithmSelect').on('change', async function() {
    // Create list of available hardware
    const hardwareList = await apiCall({algo: this.value}, '/hardware', "POST")
    let $el = $("#gearSelect");

    $('#gearSelect option:gt(0)').remove();
    $.each(hardwareList, function(key,value) {
          $el.append($("<option></option>").attr("value", value).text(key));
    });

    // Update related fields
    updateAlgo(this.value)

    await getHardware()
    await updateCalculator().then(() => {console.log('Calculator updated')})
});


// Listen for gear select changes
$('#gearSelect').on('input', async function() {
    await getHardware()
    updateCalculator().then(() => {console.log('Calculator updated')})
});


// Listen for hashrate input changes
$('#hashrate').on('input', function() {
    $('#gearSelect').val('no_id')
    updateCalculator().then(() => {console.log('Calculator updated')})
});


// Listen for input consumption changes
$('#consumption').on('input', function() {
    $('#gearSelect').val('no_id')
    updateCalculator().then(() => {console.log('Calculator updated')})
});


// Listen for currency input changes
$('#currencySelect').on('input', function() {
    const symbol = $('#currencySelect option:selected').val()

    // Update related fields
    $('.epic-price').html(spinnerHTMLsm)
    $('.flag-icon').attr('src', getFlagIcon(this.value))
    $('.currency-symbol').text(symbol)

    updateCalculator().then(() => {console.log('Calculator updated')})
});


// Listen for energy input changes
$('#energy').on('input', function() {
    updateCalculator().then(() => {console.log('Calculator updated')})
});


// Listen for pool_fee input changes
$('#pool_fee').on('input', function() {
    updateCalculator().then(() => {console.log('Calculator updated')})
});


// Listen for pool input changes
$('#poolSelect').on('input', function() {
    const pool = $('#poolSelect option:selected').val()

    // TODO: get the pool fee and img from database
    const imgURL = `${getPoolIcon(pool)}.png`
    const poolFee = 1  // dummy

    if (pool) {
        // Update related fields
        $('#poolIcon').html(`<img src="${imgURL}" alt='pool-logo' height="22" class="rounded">`)
        $('#pool_fee').val(poolFee)
    } else {
        $('#pool_fee').val(0)
        $('#poolIcon').text('')
    }

    updateCalculator().then(() => {console.log('Calculator updated')})
});

