import sys
import json
import logging

import requests
import msal

def acquire_access_token(authority, client_id, client_secret, scope):
    """
    Function to acquire AAD access token
    :param authority: Tenent URL
    :param client_id: Service Principal's client_id
    :param client_secret: Service Principal's client secret
    :param scope: OAuth2 scope - default
    :return: access_token
    """
    app = msal.ConfidentialClientApplication(
        client_id, authority=authority,
        client_credential=client_secret)

    result = None

    result = app.acquire_token_silent(scope, account=None)

    if not result:
        print("No suitable token exists in cache. Let's get a new one from AAD.")
        result = app.acquire_token_for_client(scopes=scope)

    if "access_token" in result:
        return result['access_token']

def create_spn(access_token, no_of_spns, spn_prefix, create_app_uri, create_spn_uri):
    """
    Function to create Application and Service Principal
    :param access_token: OAuth2 access token
    :param no_of_spns: No of Service Principal to be created
    :param spn_prefix: Service Principal prefix
    :param create_app_uri: Create URI to create Application object
    :param create_spn_uri: Create URI to create Service Principal object
    """
    create_spn = {}
    # Create Service Principal
    for var in list(range(1, no_of_spns + 1)):
        app_data = requests.post(
            create_app_uri,
            headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'},
            data=json.dumps({'displayName': '{}{}'.format(spn_prefix, var), 'signInAudience':'AzureADMyOrg'})).json()

        spn_data = requests.post(  # Use token to call downstream service
            create_spn_uri,
            headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'},
            data=json.dumps({'appId': app_data['appId'],'tags': ['WindowsAzureActiveDirectoryIntegratedApp']})).json()

        create_spn[spn_data['appDisplayName']] = spn_data['id']

    print("Created Service Principal: ")
    print('|{}|{}|'.format('=' * 15,'=' * 40))
    print('|{}|{}|'.format('Display Name'.ljust(15,' '),'Object ID'.ljust(40,' ')))
    print('|{}|{}|'.format('=' * 15,'=' * 40))
    for key, value in create_spn.items():
        print('|{}|{}|'.format(key.ljust(15,' '),value.ljust(40,' ')))
    print('|{}|{}|'.format('=' * 15,'=' * 40))


def create_sgp(access_token, no_of_sgps, sgp_prefix, create_sgp_uri, sgp_add_owner_uri, sgp_group_owner):
    """
    Function to create Security Groups
    :param access_token: OAuth2 access token
    :param no_of_sgps: No of Security Groups to be created
    :param sgp_prefix: Security Groups prefix
    :param create_sgp_uri: Create URI to create Security Group object
    """
    create_sgp = {}
    for var in range(1, int(no_of_sgps)+1):
        group_data = requests.post(  # Use token to call downstream service
                create_sgp_uri,
                headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'},
                data=json.dumps({'displayName': '{}{}'.format(sgp_prefix, var), 'mailEnabled': 'false', 'mailNickname': '{}{}'.format(sgp_prefix, var), 'securityEnabled': 'true'})).json()
        requests.post(
                sgp_add_owner_uri.format(group_data['id']),
                headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'},
                data=json.dumps({'@odata.id': 'https://graph.microsoft.com/v1.0/users/{}'.format(sgp_group_owner)}))
        create_sgp[group_data['displayName']] = group_data['id']

    print("Created Security Groups:")
    print('|{}|{}|'.format('=' * 15,'=' * 40))
    print('|{}|{}|'.format('Display Name'.ljust(15,' '),'Object ID'.ljust(40,' ')))
    print('|{}|{}|'.format('=' * 15,'=' * 40))
    for key, value in create_sgp.items():
        print('|{}|{}|'.format(key.ljust(15,' '),value.ljust(40,' ')))
    print('|{}|{}|'.format('=' * 15,'=' * 40))

def use_case_1_add_member(access_token, uc1_spn, create_spn_uri, spn_filter_uri, create_sgp_uri, sgp_filter_uri, sgp_prefix, sgp_add_member_uri):
    print('Use Case:1 -> Adding SPN: {} to all groups with prefix: {}'.format(uc1_spn, sgp_prefix))
    spn_to_add = requests.get(
        '{}{}'.format(create_spn_uri, spn_filter_uri.format(uc1_spn)),
                headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'}).json()
    spn_id = spn_to_add['value'][0]['id']
    graph_data = requests.get(
        '{}{}'.format(create_sgp_uri, sgp_filter_uri.format(sgp_prefix)),
                headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'}).json()
    for grp in graph_data['value']:
        requests.post(
                sgp_add_member_uri.format(grp['id']),
                headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'},
                data=json.dumps({'@odata.id': 'https://graph.microsoft.com/v1.0/directoryObjects/{}'.format(spn_id)}))

def use_case_2_add_member(create_sgp_uri, sgp_filter_uri, uc2_sgp, create_spn_uri, spn_filter_uri, spn_prefix, sgp_add_member_uri):
    print('Use Case:2 -> Adding SPN with prefix: {} to group: {}'.format(spn_prefix, uc2_sgp))
    sgp_group = requests.get(
        '{}{}'.format(create_sgp_uri, sgp_filter_uri.format(uc2_sgp)),
                headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'}).json()
    sgp_id = sgp_group['value'][0]['id']

    spn_data = requests.get(
        '{}{}'.format(create_spn_uri, spn_filter_uri.format(spn_prefix)),
                headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'}).json()
    for grp in spn_data['value']:
        requests.post(
                sgp_add_member_uri.format(sgp_id),
                headers={'Authorization': 'Bearer ' + access_token, 'Content-type': 'application/json'},
                data=json.dumps({'@odata.id': 'https://graph.microsoft.com/v1.0/directoryObjects/{}'.format(grp['id'])}))


def test(access_token, endpoint):

    graph_data = requests.get(
        endpoint,
        headers={'Authorization': 'Bearer ' + access_token}, ).json()
    print(json.dumps(graph_data, indent=2))

if __name__ == '__main__':
#     One Service Principal (Ex: SPN1) should be member of all 500 AAD Security Groups.
#     One AAD Security Group (Ex: SG2) should have all 500 SPNs as a member.
    config = json.load(open(sys.argv[1]))
    access_token = acquire_access_token(config["authority"], config["client_id"], config["secret"], config["scope"])
    create_spn(access_token, int(config["no_of_spns"]), config["spn_prefix"], config["create_app_uri"], config["create_spn_uri"])
    create_sgp(access_token, int(config["no_of_sgps"]), config["sgp_prefix"], config["create_sgp_uri"], config['sgp_add_owner_uri'], config['sgp_group_owner'])
    use_case_1_add_member(access_token, config["uc1_spn"], config["create_spn_uri"], config["spn_filter_uri"], config["create_sgp_uri"], config["sgp_filter_uri"], config["sgp_prefix"], config["sgp_add_member_uri"])
    use_case_2_add_member(config["create_sgp_uri"], config["sgp_filter_uri"], config["uc2_sgp"], config["create_spn_uri"], config["spn_filter_uri"],config["spn_prefix"], config["sgp_add_member_uri"])
    # test(access_token,'https://graph.microsoft.com/v1.0/groups/6d865abe-e764-4bda-8447-70fe4818c87f/owners')

