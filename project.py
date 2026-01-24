"""
NFT Marketplace - Smart Contract SmartPy
=========================================
Un contrat minimaliste mais sécurisé pour créer et échanger des NFTs.

Fonctionnalités:
- Mint de NFTs (payant)
- Mise en vente avec prix personnalisé
- Achat de NFTs avec royalties à l'auteur
- Transfert gratuit entre utilisateurs
- Retrait de la vente
- Administration des frais de plateforme

Auteur: DApp NFT Marketplace
Version: 1.0
"""

import smartpy as sp

@sp.module
def main():
    
    # Types personnalisés
    token_type: type = sp.record(
        metadata=sp.string,
        author=sp.address,
        owner=sp.address,
        price=sp.mutez,
        for_sale=sp.bool
    )
    
    class NFTMarketplace(sp.Contract):
        """
        Contrat principal de la marketplace NFT.
        """
        
        def __init__(self, admin, mint_price, royalty_percent, platform_fee_percent):
            # Validations initiales
            assert royalty_percent + platform_fee_percent < 100, "Fees too high"
            
            self.data.tokens = sp.cast(
                sp.big_map(), 
                sp.big_map[sp.nat, token_type]
            )
            self.data.next_id = sp.nat(0)
            self.data.admin = admin
            self.data.mint_price = mint_price
            self.data.royalty_percent = royalty_percent
            self.data.platform_fee_percent = platform_fee_percent
            self.data.collected_fees = sp.mutez(0)
            self.data.paused = False
        
        # ============== ENTRYPOINTS UTILISATEUR ==============
        
        @sp.entrypoint
        def mint(self, metadata):
            """Créer un nouveau NFT."""
            sp.cast(metadata, sp.string)
            
            assert not self.data.paused, "Contract is paused"
            assert sp.amount == self.data.mint_price, "Invalid mint price"
            
            self.data.tokens[self.data.next_id] = sp.record(
                metadata=metadata,
                author=sp.sender,
                owner=sp.sender,
                price=sp.mutez(0),
                for_sale=False
            )
            self.data.next_id += 1
            self.data.collected_fees += sp.amount
        
        @sp.entrypoint
        def list_for_sale(self, token_id, price):
            """Mettre un NFT en vente."""
            sp.cast(token_id, sp.nat)
            sp.cast(price, sp.mutez)
            
            assert not self.data.paused, "Contract is paused"
            assert self.data.tokens.contains(token_id), "Token does not exist"
            
            token = self.data.tokens[token_id]
            assert token.owner == sp.sender, "Not the owner"
            assert not token.for_sale, "Already listed for sale"
            assert price > sp.mutez(0), "Price must be greater than 0"
            
            self.data.tokens[token_id].price = price
            self.data.tokens[token_id].for_sale = True
        
        @sp.entrypoint
        def cancel_sale(self, token_id):
            """Retirer un NFT de la vente."""
            sp.cast(token_id, sp.nat)
            
            assert self.data.tokens.contains(token_id), "Token does not exist"
            
            token = self.data.tokens[token_id]
            assert token.owner == sp.sender, "Not the owner"
            assert token.for_sale, "Not listed for sale"
            
            self.data.tokens[token_id].for_sale = False
            self.data.tokens[token_id].price = sp.mutez(0)
        
        @sp.entrypoint
        def buy(self, token_id):
            """Acheter un NFT."""
            sp.cast(token_id, sp.nat)
            
            assert not self.data.paused, "Contract is paused"
            assert self.data.tokens.contains(token_id), "Token does not exist"
            
            token = self.data.tokens[token_id]
            assert token.for_sale, "Token not for sale"
            assert sp.sender != token.owner, "Cannot buy your own token"
            assert sp.amount == token.price, "Invalid price"
            
            # Calcul des parts (évite les pertes par arrondi)
            royalty_amount = sp.split_tokens(token.price, self.data.royalty_percent, 100)
            platform_fee = sp.split_tokens(token.price, self.data.platform_fee_percent, 100)
            seller_amount = token.price - royalty_amount - platform_fee
            
            # Paiements
            sp.send(token.author, royalty_amount)
            sp.send(token.owner, seller_amount)
            self.data.collected_fees += platform_fee
            
            # Transfert de propriété
            self.data.tokens[token_id].owner = sp.sender
            self.data.tokens[token_id].for_sale = False
            self.data.tokens[token_id].price = sp.mutez(0)
        
        @sp.entrypoint
        def transfer(self, token_id, new_owner):
            """Transférer un NFT gratuitement."""
            sp.cast(token_id, sp.nat)
            sp.cast(new_owner, sp.address)
            
            assert self.data.tokens.contains(token_id), "Token does not exist"
            assert sp.amount == sp.mutez(0), "No tez should be sent"
            
            token = self.data.tokens[token_id]
            assert token.owner == sp.sender, "Not the owner"
            assert new_owner != sp.sender, "Cannot transfer to yourself"
            assert not token.for_sale, "Cancel sale before transfer"
            
            self.data.tokens[token_id].owner = new_owner
        
        @sp.entrypoint
        def update_author_address(self, token_id, new_author):
            """Mettre à jour l'adresse de l'auteur pour les royalties."""
            sp.cast(token_id, sp.nat)
            sp.cast(new_author, sp.address)
            
            assert self.data.tokens.contains(token_id), "Token does not exist"
            
            token = self.data.tokens[token_id]
            assert token.author == sp.sender, "Not the author"
            assert new_author != sp.sender, "Same address"
            
            self.data.tokens[token_id].author = new_author
        
        # ============== ENTRYPOINTS ADMIN ==============
        
        @sp.entrypoint
        def withdraw_fees(self):
            """Retirer les frais accumulés (admin uniquement)."""
            assert sp.sender == self.data.admin, "Not admin"
            assert self.data.collected_fees > sp.mutez(0), "No fees to withdraw"
            
            amount = self.data.collected_fees
            self.data.collected_fees = sp.mutez(0)
            sp.send(self.data.admin, amount)
        
        @sp.entrypoint
        def set_pause(self, paused):
            """Mettre en pause ou réactiver le contrat."""
            sp.cast(paused, sp.bool)
            assert sp.sender == self.data.admin, "Not admin"
            self.data.paused = paused
        
        @sp.entrypoint
        def update_mint_price(self, new_price):
            """Mettre à jour le prix de mint."""
            sp.cast(new_price, sp.mutez)
            assert sp.sender == self.data.admin, "Not admin"
            self.data.mint_price = new_price
        
        @sp.entrypoint
        def transfer_admin(self, new_admin):
            """Transférer les droits d'administration."""
            sp.cast(new_admin, sp.address)
            assert sp.sender == self.data.admin, "Not admin"
            assert new_admin != self.data.admin, "Same admin"
            self.data.admin = new_admin
        
        # ============== VUES ==============
        
        @sp.onchain_view
        def get_token(self, token_id):
            """Récupérer les informations d'un token."""
            sp.cast(token_id, sp.nat)
            assert self.data.tokens.contains(token_id), "Token does not exist"
            return self.data.tokens[token_id]
        
        @sp.onchain_view
        def get_total_tokens(self):
            """Récupérer le nombre total de tokens."""
            return self.data.next_id
        
        @sp.onchain_view
        def is_for_sale(self, token_id):
            """Vérifier si un token est en vente."""
            sp.cast(token_id, sp.nat)
            assert self.data.tokens.contains(token_id), "Token does not exist"
            return self.data.tokens[token_id].for_sale


# ================================================================
# TESTS COMPLETS
# ================================================================

@sp.add_test()
def test_mint():
    """Test du mint de NFTs - cas normaux et edge cases."""
    scenario = sp.test_scenario("Mint Tests", main)
    
    admin = sp.test_account("admin").address
    alice = sp.test_account("alice").address
    bob = sp.test_account("bob").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    # ✅ Mint réussi
    contract.mint("NFT #1 by Alice", _sender=alice, _amount=sp.tez(1))
    scenario.verify(contract.data.next_id == 1)
    scenario.verify(contract.data.tokens[0].owner == alice)
    scenario.verify(contract.data.tokens[0].author == alice)
    scenario.verify(contract.data.collected_fees == sp.tez(1))
    
    # ✅ Second mint
    contract.mint("NFT #2 by Bob", _sender=bob, _amount=sp.tez(1))
    scenario.verify(contract.data.next_id == 2)
    
    # ❌ Mint avec montant incorrect (trop peu)
    contract.mint(
        "Invalid",
        _sender=alice,
        _amount=sp.mutez(500000),
        _valid=False,
        _exception="Invalid mint price"
    )
    
    # ❌ Mint avec montant incorrect (trop)
    contract.mint(
        "Invalid",
        _sender=alice,
        _amount=sp.tez(2),
        _valid=False,
        _exception="Invalid mint price"
    )
    
    # ❌ Mint sans paiement
    contract.mint(
        "Invalid",
        _sender=alice,
        _amount=sp.tez(0),
        _valid=False,
        _exception="Invalid mint price"
    )


@sp.add_test()
def test_list_for_sale():
    """Test de la mise en vente - cas normaux et edge cases."""
    scenario = sp.test_scenario("List For Sale Tests", main)
    
    admin = sp.test_account("admin").address
    alice = sp.test_account("alice").address
    bob = sp.test_account("bob").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    # Setup: Alice mint un NFT
    contract.mint("Alice's NFT", _sender=alice, _amount=sp.tez(1))
    
    # ✅ Mise en vente réussie
    contract.list_for_sale(token_id=0, price=sp.tez(10), _sender=alice)
    scenario.verify(contract.data.tokens[0].for_sale == True)
    scenario.verify(contract.data.tokens[0].price == sp.tez(10))
    
    # ❌ Token inexistant
    contract.list_for_sale(
        token_id=999,
        price=sp.tez(5),
        _sender=alice,
        _valid=False,
        _exception="Token does not exist"
    )
    
    # ❌ Non propriétaire essaie de vendre
    contract.mint("Bob's NFT", _sender=bob, _amount=sp.tez(1))
    contract.list_for_sale(
        token_id=1,
        price=sp.tez(5),
        _sender=alice,
        _valid=False,
        _exception="Not the owner"
    )
    
    # ❌ Déjà en vente
    contract.list_for_sale(
        token_id=0,
        price=sp.tez(20),
        _sender=alice,
        _valid=False,
        _exception="Already listed for sale"
    )
    
    # ❌ Prix à zéro
    contract.list_for_sale(
        token_id=1,
        price=sp.mutez(0),
        _sender=bob,
        _valid=False,
        _exception="Price must be greater than 0"
    )


@sp.add_test()
def test_cancel_sale():
    """Test de l'annulation de vente - cas normaux et edge cases."""
    scenario = sp.test_scenario("Cancel Sale Tests", main)
    
    admin = sp.test_account("admin").address
    alice = sp.test_account("alice").address
    bob = sp.test_account("bob").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    # Setup
    contract.mint("Alice's NFT", _sender=alice, _amount=sp.tez(1))
    contract.list_for_sale(token_id=0, price=sp.tez(10), _sender=alice)
    
    # ✅ Annulation réussie
    contract.cancel_sale(0, _sender=alice)
    scenario.verify(contract.data.tokens[0].for_sale == False)
    scenario.verify(contract.data.tokens[0].price == sp.mutez(0))
    
    # ❌ Token inexistant
    contract.cancel_sale(
        999,
        _sender=alice,
        _valid=False,
        _exception="Token does not exist"
    )
    
    # ❌ Non propriétaire
    contract.mint("Bob's NFT", _sender=bob, _amount=sp.tez(1))
    contract.list_for_sale(token_id=1, price=sp.tez(5), _sender=bob)
    contract.cancel_sale(
        1,
        _sender=alice,
        _valid=False,
        _exception="Not the owner"
    )
    
    # ❌ Token pas en vente
    contract.cancel_sale(
        0,
        _sender=alice,
        _valid=False,
        _exception="Not listed for sale"
    )


@sp.add_test()
def test_buy():
    """Test de l'achat - cas normaux et edge cases."""
    scenario = sp.test_scenario("Buy Tests", main)
    
    admin = sp.test_account("admin").address
    alice = sp.test_account("alice").address
    bob = sp.test_account("bob").address
    charlie = sp.test_account("charlie").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    # Setup: Alice mint et met en vente
    contract.mint("Alice's NFT", _sender=alice, _amount=sp.tez(1))
    contract.list_for_sale(token_id=0, price=sp.tez(10), _sender=alice)
    
    # Vérification des fees initiales (1 tez du mint)
    scenario.verify(contract.data.collected_fees == sp.tez(1))
    
    # ✅ Achat réussi par Bob
    contract.buy(0, _sender=bob, _amount=sp.tez(10))
    scenario.verify(contract.data.tokens[0].owner == bob)
    scenario.verify(contract.data.tokens[0].for_sale == False)
    # Fees: 1 tez (mint) + 0.2 tez (2% de 10 tez) = 1.2 tez
    scenario.verify(contract.data.collected_fees == sp.mutez(1200000))
    
    # ❌ Token inexistant
    contract.buy(
        999,
        _sender=charlie,
        _amount=sp.tez(10),
        _valid=False,
        _exception="Token does not exist"
    )
    
    # ❌ Token pas en vente
    contract.buy(
        0,
        _sender=charlie,
        _amount=sp.tez(10),
        _valid=False,
        _exception="Token not for sale"
    )
    
    # Bob remet en vente
    contract.list_for_sale(token_id=0, price=sp.tez(20), _sender=bob)
    
    # ❌ Acheter son propre token
    contract.buy(
        0,
        _sender=bob,
        _amount=sp.tez(20),
        _valid=False,
        _exception="Cannot buy your own token"
    )
    
    # ❌ Mauvais prix (trop peu)
    contract.buy(
        0,
        _sender=charlie,
        _amount=sp.tez(19),
        _valid=False,
        _exception="Invalid price"
    )
    
    # ❌ Mauvais prix (trop)
    contract.buy(
        0,
        _sender=charlie,
        _amount=sp.tez(21),
        _valid=False,
        _exception="Invalid price"
    )


@sp.add_test()
def test_royalties():
    """Test du calcul correct des royalties et frais."""
    scenario = sp.test_scenario("Royalties Tests", main)
    
    admin = sp.test_account("admin").address
    author = sp.test_account("author").address
    buyer1 = sp.test_account("buyer1").address
    buyer2 = sp.test_account("buyer2").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    # L'auteur mint et vend
    contract.mint("Artwork", _sender=author, _amount=sp.tez(1))
    contract.list_for_sale(token_id=0, price=sp.tez(100), _sender=author)
    
    # Premier achat (100 tez)
    contract.buy(0, _sender=buyer1, _amount=sp.tez(100))
    
    # Fees: 1 (mint) + 2 (platform 2%) = 3 tez
    scenario.verify(contract.data.collected_fees == sp.tez(3))
    
    # Buyer1 revend
    contract.list_for_sale(token_id=0, price=sp.tez(200), _sender=buyer1)
    
    # Second achat (200 tez)
    # L'auteur original reçoit toujours ses 5% = 10 tez
    contract.buy(0, _sender=buyer2, _amount=sp.tez(200))
    
    # Fees: 3 + 4 = 7 tez
    scenario.verify(contract.data.collected_fees == sp.tez(7))
    scenario.verify(contract.data.tokens[0].author == author)


@sp.add_test()
def test_transfer():
    """Test du transfert gratuit - cas normaux et edge cases."""
    scenario = sp.test_scenario("Transfer Tests", main)
    
    admin = sp.test_account("admin").address
    alice = sp.test_account("alice").address
    bob = sp.test_account("bob").address
    charlie = sp.test_account("charlie").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    contract.mint("Alice's NFT", _sender=alice, _amount=sp.tez(1))
    
    # ✅ Transfert réussi
    contract.transfer(token_id=0, new_owner=bob, _sender=alice)
    scenario.verify(contract.data.tokens[0].owner == bob)
    scenario.verify(contract.data.tokens[0].author == alice)
    
    # ❌ Token inexistant
    contract.transfer(
        token_id=999,
        new_owner=charlie,
        _sender=bob,
        _valid=False,
        _exception="Token does not exist"
    )
    
    # ❌ Non propriétaire
    contract.transfer(
        token_id=0,
        new_owner=charlie,
        _sender=alice,
        _valid=False,
        _exception="Not the owner"
    )
    
    # ❌ Transfert à soi-même
    contract.transfer(
        token_id=0,
        new_owner=bob,
        _sender=bob,
        _valid=False,
        _exception="Cannot transfer to yourself"
    )
    
    # ❌ Transfert avec tez envoyés
    contract.transfer(
        token_id=0,
        new_owner=charlie,
        _sender=bob,
        _amount=sp.tez(1),
        _valid=False,
        _exception="No tez should be sent"
    )
    
    # ❌ Transfert d'un token en vente
    contract.list_for_sale(token_id=0, price=sp.tez(5), _sender=bob)
    contract.transfer(
        token_id=0,
        new_owner=charlie,
        _sender=bob,
        _valid=False,
        _exception="Cancel sale before transfer"
    )


@sp.add_test()
def test_update_author():
    """Test de la mise à jour de l'adresse auteur."""
    scenario = sp.test_scenario("Update Author Tests", main)
    
    admin = sp.test_account("admin").address
    alice = sp.test_account("alice").address
    bob = sp.test_account("bob").address
    new_wallet = sp.test_account("new_wallet").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    contract.mint("Alice's NFT", _sender=alice, _amount=sp.tez(1))
    
    # ✅ Mise à jour réussie
    contract.update_author_address(token_id=0, new_author=new_wallet, _sender=alice)
    scenario.verify(contract.data.tokens[0].author == new_wallet)
    
    # ❌ Token inexistant
    contract.update_author_address(
        token_id=999,
        new_author=bob,
        _sender=alice,
        _valid=False,
        _exception="Token does not exist"
    )
    
    # ❌ Non auteur
    contract.update_author_address(
        token_id=0,
        new_author=bob,
        _sender=alice,
        _valid=False,
        _exception="Not the author"
    )
    
    # ❌ Même adresse
    contract.update_author_address(
        token_id=0,
        new_author=new_wallet,
        _sender=new_wallet,
        _valid=False,
        _exception="Same address"
    )


@sp.add_test()
def test_admin_functions():
    """Test des fonctions administrateur."""
    scenario = sp.test_scenario("Admin Tests", main)
    
    admin = sp.test_account("admin").address
    new_admin = sp.test_account("new_admin").address
    alice = sp.test_account("alice").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    # Générer des fees
    contract.mint("NFT", _sender=alice, _amount=sp.tez(1))
    scenario.verify(contract.data.collected_fees == sp.tez(1))
    
    # ❌ Non-admin essaie de retirer
    contract.withdraw_fees(_sender=alice, _valid=False, _exception="Not admin")
    
    # ✅ Admin retire les fees
    contract.withdraw_fees(_sender=admin)
    scenario.verify(contract.data.collected_fees == sp.mutez(0))
    
    # ❌ Pas de fees à retirer
    contract.withdraw_fees(_sender=admin, _valid=False, _exception="No fees to withdraw")
    
    # ✅ Mise en pause
    contract.set_pause(True, _sender=admin)
    scenario.verify(contract.data.paused == True)
    
    # ❌ Mint en pause
    contract.mint(
        "Blocked",
        _sender=alice,
        _amount=sp.tez(1),
        _valid=False,
        _exception="Contract is paused"
    )
    
    # ✅ Réactivation
    contract.set_pause(False, _sender=admin)
    
    # ✅ Changement de prix de mint
    contract.update_mint_price(sp.tez(2), _sender=admin)
    scenario.verify(contract.data.mint_price == sp.tez(2))
    
    # ❌ Non-admin change le prix
    contract.update_mint_price(
        sp.tez(5),
        _sender=alice,
        _valid=False,
        _exception="Not admin"
    )
    
    # ✅ Transfert d'admin
    contract.transfer_admin(new_admin, _sender=admin)
    scenario.verify(contract.data.admin == new_admin)
    
    # ❌ Ancien admin ne peut plus agir
    contract.set_pause(True, _sender=admin, _valid=False, _exception="Not admin")
    
    # ❌ Transfert vers soi-même
    contract.transfer_admin(
        new_admin,
        _sender=new_admin,
        _valid=False,
        _exception="Same admin"
    )


@sp.add_test()
def test_edge_cases_rounding():
    """Test des cas limites avec arrondis."""
    scenario = sp.test_scenario("Rounding Edge Cases", main)
    
    admin = sp.test_account("admin").address
    alice = sp.test_account("alice").address
    bob = sp.test_account("bob").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.mutez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    # Mint avec 1 mutez
    contract.mint("Tiny NFT", _sender=alice, _amount=sp.mutez(1))
    
    # Vente à 1 mutez (cas extrême d'arrondi)
    contract.list_for_sale(token_id=0, price=sp.mutez(1), _sender=alice)
    
    # Achat - les arrondis donnent 0 pour royalties et fees
    contract.buy(0, _sender=bob, _amount=sp.mutez(1))
    scenario.verify(contract.data.tokens[0].owner == bob)


@sp.add_test()
def test_full_workflow():
    """Test d'un workflow complet réaliste."""
    scenario = sp.test_scenario("Full Workflow", main)
    
    admin = sp.test_account("admin").address
    artist = sp.test_account("artist").address
    collector1 = sp.test_account("collector1").address
    collector2 = sp.test_account("collector2").address
    collector3 = sp.test_account("collector3").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=10,
        platform_fee_percent=3
    )
    scenario += contract
    
    # 1. L'artiste crée son œuvre
    contract.mint("ipfs://QmArtwork123", _sender=artist, _amount=sp.tez(1))
    
    # 2. L'artiste met en vente
    contract.list_for_sale(token_id=0, price=sp.tez(50), _sender=artist)
    
    # 3. Collector1 achète
    contract.buy(0, _sender=collector1, _amount=sp.tez(50))
    
    # 4. Collector1 revend plus cher
    contract.list_for_sale(token_id=0, price=sp.tez(100), _sender=collector1)
    
    # 5. Collector2 achète
    contract.buy(0, _sender=collector2, _amount=sp.tez(100))
    
    # 6. Collector2 décide de donner le NFT
    contract.transfer(token_id=0, new_owner=collector3, _sender=collector2)
    
    # 7. Vérifications finales
    scenario.verify(contract.data.tokens[0].owner == collector3)
    scenario.verify(contract.data.tokens[0].author == artist)
    
    # 8. L'admin retire les fees
    # Fees: 1 (mint) + 1.5 (3% de 50) + 3 (3% de 100) = 5.5 tez
    scenario.verify(contract.data.collected_fees == sp.mutez(5500000))
    contract.withdraw_fees(_sender=admin)


@sp.add_test()
def test_multiple_tokens():
    """Test avec plusieurs tokens pour vérifier l'isolation."""
    scenario = sp.test_scenario("Multiple Tokens Isolation", main)
    
    admin = sp.test_account("admin").address
    alice = sp.test_account("alice").address
    bob = sp.test_account("bob").address
    
    contract = main.NFTMarketplace(
        admin=admin,
        mint_price=sp.tez(1),
        royalty_percent=5,
        platform_fee_percent=2
    )
    scenario += contract
    
    # Créer plusieurs NFTs
    contract.mint("NFT 0", _sender=alice, _amount=sp.tez(1))
    contract.mint("NFT 1", _sender=alice, _amount=sp.tez(1))
    contract.mint("NFT 2", _sender=bob, _amount=sp.tez(1))
    
    # Vendre seulement le NFT 1
    contract.list_for_sale(token_id=1, price=sp.tez(10), _sender=alice)
    
    # Vérifier que les autres ne sont pas affectés
    scenario.verify(contract.data.tokens[0].for_sale == False)
    scenario.verify(contract.data.tokens[1].for_sale == True)
    scenario.verify(contract.data.tokens[2].for_sale == False)
    
    # Bob achète NFT 1
    contract.buy(1, _sender=bob, _amount=sp.tez(10))
    
    # Vérifier l'isolation
    scenario.verify(contract.data.tokens[0].owner == alice)
    scenario.verify(contract.data.tokens[1].owner == bob)
    scenario.verify(contract.data.tokens[2].owner == bob)